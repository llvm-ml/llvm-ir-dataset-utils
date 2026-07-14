"""Module for building and extracting bitcode from applications using Portage"""

import subprocess
import os
import logging
import pathlib
import shutil
import ray

from mlgo.corpus import extract_ir_lib

from llvm_ir_dataset_utils.util import portage as portage_utils
from llvm_ir_dataset_utils.util import extract_source_lib

BUILD_LOG_NAME = './portage_build.log'


def get_spec_command_vector_section(spec):
  return spec.split(' ')


def generate_emerge_command(package_to_build, threads, build_dir):
  command_vector = [
      'emerge',  # Portage package management command
      '--jobs={}'.format(
          threads),  # Set the number of jobs for parallel building
      '--load-average={}'.format(
          threads),  # Set the maximum load average for parallel builds
      '--config-root={}'.format(
          build_dir),  # Set the configuration root directory
      '--oneshot',  # Do not add corpus targets to the container's world set
      '--buildpkg',  # Build binary packages, similar to Spack's build cache
      '--usepkg',  # Use binary packages if available
      '--usepkg-exclude',
      package_to_build,  # Always rebuild the corpus target from source
      package_to_build  # The package to install
  ]

  # Portage does not support setting the build directory directly in the command,
  # but this can be controlled with the PORTAGE_TMPDIR environment variable
  # This environment variable needs to be set when calling subprocess, not here directly
  return command_vector


def perform_build(package_name, assembled_build_command, corpus_dir, build_dir):
  logging.info(f"Portage building package {package_name}")

  environment = os.environ.copy()
  environment['DISTDIR'] = str(build_dir)
  environment['PORTAGE_TMPDIR'] = str(build_dir)

  build_log_path = os.path.join(corpus_dir, BUILD_LOG_NAME)

  try:
    with open(build_log_path, 'w') as build_log_file:
      subprocess.run(
          assembled_build_command,
          stdout=build_log_file,
          stderr=build_log_file,
          check=True,
          env=environment)
  except subprocess.CalledProcessError:
    logging.warning(f"Failed to build portage package {package_name}")
    return False

  logging.info(f"Finished building portage package {package_name}")
  return True


def get_package_work_directory(package_spec, package_name, build_dir):
  if '/' not in package_spec:
    raise ValueError(
        f'Portage package spec must contain a category: {package_spec}')

  category = package_spec.lstrip('<>=~').split('/', maxsplit=1)[0]
  category_build_directory = pathlib.Path(build_dir) / 'portage' / category
  candidates = [
      package_directory / 'work'
      for package_directory in category_build_directory.glob(
          f'{package_name}-[0-9]*')
      if (package_directory / 'work').is_dir()
  ]

  if len(candidates) != 1:
    candidate_list = ', '.join(str(candidate) for candidate in candidates)
    raise RuntimeError(
        f'Expected one Portage work directory for {package_spec}, found '
        f'{len(candidates)}: {candidate_list}')

  return candidates[0]


def extract_ir(package_spec, package_name, corpus_dir, build_dir, threads):
  build_directory = get_package_work_directory(package_spec, package_name,
                                               build_dir)
  objects = extract_ir_lib.load_from_directory(build_directory, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(objects, threads,
                                                        "llvm-objcopy", None,
                                                        None, ".llvmcmd",
                                                        ".llvmbc")
  extracted_modules = [
      path for path in relative_output_paths if path is not None
  ]
  if not extracted_modules:
    raise RuntimeError(f'No LLVM IR was extracted for {package_spec}')

  extract_ir_lib.write_corpus_manifest(None, extracted_modules, corpus_dir)
  extract_source_lib.copy_source(build_directory, corpus_dir)
  return extracted_modules


def cleanup(build_dir):
  shutil.rmtree(build_dir)


def record_failure(corpus_dir, message):
  build_log_path = os.path.join(corpus_dir, BUILD_LOG_NAME)
  with open(build_log_path, 'a') as build_log_file:
    build_log_file.write(f'\n{message}\n')


def construct_build_log(build_success, package_name):
  return {
      'targets': [{
          'name': package_name,
          'build_log': BUILD_LOG_NAME,
          'success': build_success
      }]
  }


def build_package(dependency_futures,
                  package_name,
                  package_spec,
                  corpus_dir,
                  threads,
                  buildcache_dir,
                  build_dir,
                  cleanup_build=False):
  dependency_futures = ray.get(dependency_futures)
  for dependency_future in dependency_futures:
    if not dependency_future['targets'][0]['success']:
      logging.warning(
          f"Dependency {dependency_future['targets'][0]['name']} failed to build "
          f"for package {package_name}, not building.")
      if cleanup_build:
        try:
          cleanup(build_dir)
        except OSError:
          logging.exception('Failed to clean Portage build directory %s',
                            build_dir)
      return construct_build_log(False, package_name)

  build_result = False
  try:
    portage_utils.portage_setup_compiler(build_dir)
    build_command = generate_emerge_command(package_spec, threads, build_dir)
    build_result = perform_build(package_name, build_command, corpus_dir,
                                 build_dir)
    if build_result:
      extract_ir(package_spec, package_name, corpus_dir, build_dir, threads)
      logging.info(f'Finished building and extracting {package_name}')
  except Exception as error:
    build_result = False
    logging.exception('Failed to build or extract Portage package %s',
                      package_name)
    record_failure(corpus_dir, f'{type(error).__name__}: {error}')
  finally:
    if cleanup_build:
      try:
        cleanup(build_dir)
      except OSError:
        logging.exception('Failed to clean Portage build directory %s',
                          build_dir)

  return construct_build_log(build_result, package_name)

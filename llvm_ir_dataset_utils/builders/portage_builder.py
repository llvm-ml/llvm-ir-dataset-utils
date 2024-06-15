"""Module for building and extracting bitcode from applications using Portage"""

import subprocess
import os
import glob
import tempfile
import logging
import pathlib
import shutil
import re
import getpass
import ray

from mlgo.corpus import extract_ir_lib

from llvm_ir_dataset_utils.util import file
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
      '--buildpkg',  # Build binary packages, similar to Spack's build cache
      '--usepkg',  # Use binary packages if available
      '--binpkg-respect-use=y',  # Ensure that binary package installations respect USE flag settings
      '--quiet-build=y',  # Reduce output during the build process
      package_to_build  # The package to install
  ]

  # Portage does not support setting the build directory directly in the command,
  # but this can be controlled with the PORTAGE_TMPDIR environment variable
  # This environment variable needs to be set when calling subprocess, not here directly
  return command_vector


def perform_build(package_name, assembled_build_command, corpus_dir, build_dir):
  logging.info(f"Portage building package {package_name}")
  environment = os.environ.copy()
  # Set DISTDIR and PORTAGE_TMPDIR to set the build directory for Portage
  environment['DISTDIR'] = build_dir
  environment['PORTAGE_TMPDIR'] = build_dir
  build_log_path = os.path.join(corpus_dir, BUILD_LOG_NAME)
  try:
    with open(build_log_path, 'w') as build_log_file:
      subprocess.run(
          assembled_build_command,
          stdout=build_log_file,
          stderr=build_log_file,
          check=True,
          env=environment)
  except subprocess.SubprocessError:
    logging.warn(f"Failed to build portage package {package_name}")
    return False
  logging.info(f"Finished build portage package {package_name}")
  return True


def extract_ir(package_spec, corpus_dir, build_dir, threads):
  build_directory = build_dir + "/portage/"
  package_spec = package_spec + "*"
  match = glob.glob(os.path.join(build_directory, package_spec))
  assert (len(match) == 1)
  package_name_with_version = os.path.basename(match[0])
  build_directory = match[0] + "/work/" + package_name_with_version
  if build_directory is not None:
    objects = extract_ir_lib.load_from_directory(build_directory, corpus_dir)
    relative_output_paths = extract_ir_lib.run_extraction(
        objects, threads, "llvm-objcopy", None, None, ".llvmcmd", ".llvmbc")
    extract_ir_lib.write_corpus_manifest(None, relative_output_paths,
                                         corpus_dir)
    extract_source_lib.copy_source(build_directory, corpus_dir)


def cleanup(package_name, package_spec, corpus_dir, uninstall=True):
  #TODO: Implement cleanup
  return


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
        cleanup(package_name, package_spec, corpus_dir, uninstall=False)
      return construct_build_log(False, package_name, None)
  portage_utils.portage_setup_compiler(build_dir)
  portage_utils.clean_binpkg(package_spec)
  build_command = generate_emerge_command(package_spec, threads, build_dir)
  build_result = perform_build(package_name, build_command, corpus_dir,
                               build_dir)
  if build_result:
    extract_ir(package_spec, corpus_dir, build_dir, threads)
    logging.warning(f'Finished building {package_name}')
  if cleanup_build:
    if build_result:
      cleanup(package_name, package_spec, corpus_dir)
    else:
      cleanup(package_name, package_spec, corpus_dir, uninstall=False)
  return construct_build_log(build_result, package_name)

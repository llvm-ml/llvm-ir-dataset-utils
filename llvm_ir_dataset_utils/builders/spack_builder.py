"""Module for building and extracting bitcode from applications using spack"""

import subprocess
import os
import tempfile
import logging
import pathlib

import ray

from compiler_opt.tools import extract_ir_lib

from llvm_ir_dataset_utils.util import file

SPACK_THREAD_OVERSUBSCRIPTION_FACTOR = 2

# TODO(boomanaiden154): Change this to adapt to the compiler version and also
# probably refactor it into a utility so that it can be easily used in the
# get_spack_package_list.py script.
SPACK_COMPILER_CONFIG = """compilers:
- compiler:
    spec: clang@=16.0.6
    paths:
      cc: /usr/bin/clang
      cxx: /usr/bin/clang++
      f77: /usr/bin/gfortran
      fc: /usr/bin/gfortran
    flags:
      cflags: -Xclang -fembed-bitcode=all
      cxxflags: -Xclang -fembed-bitcode=all
    operating_system: ubuntu22.04
    target: x86_64
    modules: []
    environment: {}
    extra_rpaths: []
"""

SPACK_GARBAGE_COLLECTION_TIMEOUT = 300


def get_spec_command_vector_section(spec):
  return spec.split(' ')


def generate_build_command(package_to_build, threads, build_dir):
  command_vector = [
      'spack', '-c', f'config:build_stage:{build_dir}', 'install',
      '--keep-stage', '--overwrite', '-y', '--use-buildcache',
      'package:never,dependencies:only', '-j',
      f'{SPACK_THREAD_OVERSUBSCRIPTION_FACTOR * threads}',
      '--no-check-signature', '--deprecated'
  ]
  command_vector.extend(get_spec_command_vector_section(package_to_build))
  return command_vector


def get_build_log_path(corpus_dir):
  return os.path.join(corpus_dir, 'spack_build.log')


def perform_build(package_name, assembled_build_command, corpus_dir, build_dir):
  logging.info(f"Spack building package {package_name}")
  environment = os.environ.copy()
  # Set $HOME to the build directory so that spack doesn't run into weird
  # errors with multiple machines trying to write to a common home directory.
  environment['HOME'] = build_dir
  try:
    with open(get_build_log_path(corpus_dir), 'w') as build_log_file:
      subprocess.run(
          assembled_build_command,
          stdout=build_log_file,
          stderr=build_log_file,
          check=True,
          env=environment)
  except subprocess.SubprocessError:
    logging.warn(f"Failed to build spack package {package_name}")
    return False
  logging.info(f"Finished build spack package {package_name}")
  return True


def get_spack_stage_directory(package_hash, build_dir):
  spack_build_directory = os.path.join(build_dir, os.getlogin())
  if not os.path.exists(spack_build_directory):
    logging.warning(os.listdir(build_dir))
    return None
  spack_stages = os.listdir(spack_build_directory)
  spack_stages.append('')
  for spack_stage_dir in spack_stages:
    if package_hash in spack_stage_dir:
      break
  # spack_stage_dir now contains the name of the directory,  or None if we
  # failed to find a stage directory (i.e., due to build failure)
  if spack_stage_dir == '':
    logging.warning(f'Failed to get stage dir for {package_hash}. This might '
                    'have been caused by your spack installation and the '
                    'package_list.json becoming out of sync.')
    return None
  return os.path.join(spack_build_directory, spack_stage_dir)


def extract_ir(package_hash, corpus_dir, build_dir, threads):
  build_directory = get_spack_stage_directory(package_hash, build_dir)
  if build_directory is not None:
    current_verbosity = logging.getLogger().getEffectiveLevel()
    logging.getLogger().setLevel(logging.ERROR)
    objects = extract_ir_lib.load_from_directory(build_directory, corpus_dir)
    relative_output_paths = extract_ir_lib.run_extraction(
        objects, threads, "llvm-objcopy", None, None, ".llvmcmd", ".llvmbc")
    extract_ir_lib.write_corpus_manifest(None, relative_output_paths,
                                         corpus_dir)
    logging.getLogger().setLevel(current_verbosity)


def push_to_buildcache(package_spec, buildcache_dir, corpus_dir):
  command_vector = [
      'spack', 'buildcache', 'push', '--unsigned', '--allow-root', '--only',
      'package', buildcache_dir
  ]
  command_vector.extend(get_spec_command_vector_section(package_spec))
  buildcache_push_log_path = os.path.join(corpus_dir, 'buildcache_push.log')
  with open(buildcache_push_log_path, 'w') as buildcache_push_log_file:
    subprocess.run(
        command_vector,
        check=True,
        stdout=buildcache_push_log_file,
        stderr=buildcache_push_log_file)


def cleanup(package_name, package_spec, corpus_dir, uninstall=True):
  if uninstall:
    uninstall_command_vector = ['spack', 'uninstall', '-y']
    uninstall_command_vector.extend(
        get_spec_command_vector_section(package_spec))
    uninstall_log_path = os.path.join(corpus_dir, 'uninstall.log')
    with open(uninstall_log_path, 'w') as uninstall_log_file:
      subprocess.run(
          uninstall_command_vector,
          check=True,
          stdout=uninstall_log_file,
          stderr=uninstall_log_file)
  # Garbage collect dependencies
  try:
    gc_command_vector = ['spack', 'gc', '-y']
    gc_log_path = os.path.join(corpus_dir, 'gc.log')
    with open(gc_log_path, 'w') as gc_log_file:
      subprocess.run(
          gc_command_vector,
          check=True,
          stdout=gc_log_file,
          stderr=gc_log_file,
          timeout=SPACK_GARBAGE_COLLECTION_TIMEOUT)
  except subprocess.SubprocessError:
    logging.warning(
        f'Failed to garbage collect while cleaning up package {package_name}.')


def construct_build_log(build_success, package_name, build_log_path):
  return {
      'targets': [{
          'name': package_name,
          'build_log': build_log_path,
          'success': build_success
      }]
  }


def spack_add_mirror(build_dir, buildcache_dir):
  environment = os.environ.copy()
  environment['HOME'] = build_dir
  command_vector = ['spack', 'mirror', 'add', 'buildcache', buildcache_dir]
  subprocess.run(
      command_vector,
      check=True,
      env=environment,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL)


def spack_setup_compiler(build_dir):
  # TODO(boomanaiden154): The following path is variable depending upon the
  # system. For example, on some systems itis ~/.spack/linux and on others it
  # is ~/.spack/cray. We should grab this path more intelligently from spack
  # somehow.
  compiler_config_path = os.path.join(build_dir, '.spack/linux/compilers.yaml')
  pathlib.Path(os.path.dirname(compiler_config_path)).mkdir(parents=True)
  with open(compiler_config_path, 'w') as compiler_config_file:
    compiler_config_file.writelines(SPACK_COMPILER_CONFIG)


def spack_setup_bootstrap_root(build_dir):
  # TODO(boomanaiden154): Pull out the hardcoded /tmp/spack-boostrap path and
  # make it a configurable somewhere.
  command_vector = ['spack', 'bootstrap', 'root', '/tmp/spack-bootstrap']
  environment = os.environ.copy()
  environment['HOME'] = build_dir
  subprocess.run(
      command_vector,
      env=environment,
      check=True,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL)


def build_package(dependency_futures,
                  package_name,
                  package_spec,
                  package_hash,
                  corpus_dir,
                  threads,
                  buildcache_dir,
                  build_dir,
                  cleanup_build=False):
  dependency_futures = ray.get(dependency_futures)
  for dependency_future in dependency_futures:
    if dependency_future['targets'][0]['success'] != True:
      logging.warning(
          f'Dependency {dependency_future["targets"][0]["name"]} failed to build for package {package_name}, not building.'
      )
      if cleanup_build:
        cleanup(package_name, package_spec, corpus_dir, uninstall=False)
      return construct_build_log(False, package_name, None)
  spack_add_mirror(build_dir, buildcache_dir)
  spack_setup_compiler(build_dir)
  spack_setup_bootstrap_root(build_dir)
  build_command = generate_build_command(package_spec, threads, build_dir)
  build_result = perform_build(package_name, build_command, corpus_dir,
                               build_dir)
  if build_result:
    extract_ir(package_hash, corpus_dir, build_dir, threads)
    push_to_buildcache(package_spec, buildcache_dir, corpus_dir)
    logging.warning(f'Finished building {package_name}')
  if cleanup_build:
    if build_result:
      cleanup(package_name, package_spec, corpus_dir, package_hash)
    else:
      cleanup(package_name, package_spec, corpus_dir, uninstall=False)
  return construct_build_log(build_result, package_name,
                             get_build_log_path(corpus_dir))

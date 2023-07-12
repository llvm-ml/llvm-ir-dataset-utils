"""Module for building and extracting bitcode from applications using spack"""

import subprocess
import os
import tempfile
import shutil

from absl import logging

from compiler_opt.tools import extract_ir_lib


def get_spec_command_vector_section(spec):
  return spec.split(' ')


def generate_build_command(package_to_build):
  command_vector = [
      'spack', 'install', '--keep-stage', '--overwrite', '-y',
      '--use-buildcache', 'package:never,dependencies:only', '-j', '16',
      '--no-check-signature'
  ]
  command_vector.extend(get_spec_command_vector_section(package_to_build))
  return command_vector


def perform_build(package_name, assembled_build_command, corpus_dir):
  logging.info(f"Spack building package {package_name}")
  try:
    with open(os.path.join(corpus_dir, 'spack_build.log'),
              'w') as build_log_file:
      subprocess.run(
          assembled_build_command,
          stdout=build_log_file,
          stderr=build_log_file,
          check=True)
  except subprocess.SubprocessError:
    logging.warn(f"Failed to build spack package {package_name}")
    return False
  logging.info(f"Finished build spack package {package_name}")
  return True


def get_spack_stage_directory(package_name):
  # TODO(boomanaiden154): It feels like tempfile.gettempdir() might be a little
  # bit flaky. Do some investigation on whether this is the case/alternatives.
  spack_build_directory = os.path.join(tempfile.gettempdir(), 'spack-stage')
  spack_stages = os.listdir(spack_build_directory)
  for spack_stage_dir in spack_stages:
    if package_name in spack_stage_dir:
      break
  # spack_stage_dir now contains the name of the directory
  return os.path.join(spack_build_directory, spack_stage_dir)


def extract_ir(package_name, corpus_dir, threads):
  stage_directory = get_spack_stage_directory(package_name)
  build_directory = os.path.join(stage_directory, 'spack-src')
  objects = extract_ir_lib.load_from_directory(build_directory, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(objects, threads,
                                                        "llvm-objcopy", None,
                                                        None, ".llvmcmd",
                                                        ".llvmbc")
  extract_ir_lib.write_corpus_manifest(None, relative_output_paths, corpus_dir)


def push_to_buildcache(package_spec):
  command_vector = [
      'spack', 'buildcache', 'push', '--unsigned', '--allow-root',
      '/tmp/buildcache'
  ]
  command_vector.extend(get_spec_command_vector_section(package_spec))
  subprocess.run(
      command_vector,
      check=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE)


def cleanup(package_name, package_spec, corpus_dir):
  uninstall_command_vector = ['spack', 'uninstall', '-y']
  uninstall_command_vector.extend(get_spec_command_vector_section(package_spec))
  uninstall_log_path = os.path.join(corpus_dir, 'uninstall.log')
  with open(uninstall_log_path, 'w') as uninstall_log_file:
    subprocess.run(
        uninstall_command_vector,
        check=True,
        stdout=uninstall_log_file,
        stderr=uninstall_log_file)
  try:
    gc_command_vector = ['spack', 'gc', '-y']
    gc_log_path = os.path.join(corpus_dir, 'gc.log')
    with open(gc_log_path, 'w') as gc_log_file:
      subprocess.run(
          gc_command_vector, check=True, stdout=gc_log_file, stderr=gc_log_file)
  except subprocess.SubprocessError:
    logging.warning('Failed to garbage collect.')
  spack_build_directory = get_spack_stage_directory(package_name)
  shutil.rmtree(spack_build_directory)

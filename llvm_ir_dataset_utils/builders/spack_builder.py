"""Module for building and extracting bitcode from applications using spack"""

import subprocess
import os
import tempfile

from absl import logging

from compiler_opt.tools import extract_ir_lib


def generate_build_command(package_to_build):
  command_vector = [
      'spack', 'install', '--keep-stage', '--overwrite', '-y',
      '--use-buildcache', 'package:never,dependencies:only', '-j', '16'
  ]
  command_vector.extend(package_to_build.split(' '))
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


def extract_ir(package_name, corpus_dir, threads):
  # TODO(boomanaiden154): It feels like tempfile.gettempdir() might be a little
  # bit flaky. Do some investigation on whether this is the case/alternatives.
  spack_build_directory = os.path.join(tempfile.gettempdir(), 'spack-stage')
  spack_stages = os.listdir(spack_build_directory)
  for spack_stage_dir in spack_stages:
    if package_name in spack_stage_dir:
      break
  # spack_stage_dir now contains the name of the directory
  build_directory = os.path.join(spack_build_directory, spack_stage_dir,
                                 'spack-src')
  objects = extract_ir_lib.load_from_directory(build_directory, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(objects, threads,
                                                        "llvm-objcopy", None,
                                                        None, ".llvmcmd",
                                                        ".llvmbc")
  extract_ir_lib.write_corpus_manifest(None, relative_output_paths, corpus_dir)


def cleanup(package_name):
  uninstall_command_vector = ["spack", "uninstall", package_name]
  subprocess.run(
      uninstall_command_vector,
      check=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE)
  clean_command_vector = ["spack", "clean", "--stage"]
  subprocess.run(
      clean_command_vector,
      check=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE)

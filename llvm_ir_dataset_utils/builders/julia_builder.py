"""Module for building and extracting bitcode from Julia applications"""

import subprocess
import os
import pathlib
import json
import logging

from compiler_opt.tools import make_corpus_lib

ARCHIVE_NAME = 'bitcode.a'
"""
Generates the command to compile a bitcode archive from a Julia package.
The archive then needs to be unpacked with `ar -x`.
"""


def generate_build_command(package_to_build, thread_count):
  command_vector = [
      "julia",
      "--threads",
      f"{thread_count}",
      "--quiet",
  ]

  # Close out the Julia command line switches
  command_vector.append("--")

  julia_builder_jl_path = os.path.join(
      os.path.dirname(__file__), 'julia_builder.jl')
  command_vector.append(julia_builder_jl_path)

  # Add the package to build
  command_vector.append(package_to_build)

  return command_vector


def perform_build(package_name, build_dir, corpus_dir, thread_count):
  build_command_vector = generate_build_command(package_name, thread_count)

  build_log_name = f'./{package_name}.build.log'
  build_log_path = os.path.join(corpus_dir, build_log_name)

  environment = os.environ.copy()
  julia_depot_path = os.path.join(build_dir, 'julia_depot')
  environment['JULIA_DEPOT_PATH'] = julia_depot_path
  environment['JULIA_PKG_SERVER'] = ''

  try:
    with open(build_log_path, 'w') as build_log_file:
      subprocess.run(
          build_command_vector,
          cwd=build_dir,
          stdout=build_log_file,
          stderr=build_log_file,
          env=environment,
          check=True)
  except subprocess.SubprocessError:
    logging.warn(f'Failed to build julia package {package_name}')
    build_success = False
  else:
    build_success = True
  if build_success:
    extract_ir(build_dir, corpus_dir)
  return {
      'targets': [{
          'success': build_success,
          'build_log': build_log_name,
          'name': package_name
      }]
  }


def unpack_archive(build_dir):
  archive_path = os.path.join(build_dir, ARCHIVE_NAME)

  # TODO(boomanaiden154): Maybe move to llvm-ar at some point?
  command_vector = ['ar', '-x', archive_path]

  subprocess.run(command_vector, cwd=build_dir)


def extract_ir(build_dir, corpus_dir):
  unpack_archive(build_dir)
  relative_paths = make_corpus_lib.load_bitcode_from_directory(build_dir)
  make_corpus_lib.copy_bitcode(relative_paths, build_dir, corpus_dir)
  make_corpus_lib.write_corpus_manifest(relative_paths, corpus_dir, '')

"""Module for building and extracting bitcode from Swift packages."""

import subprocess
import os
import logging

from compiler_opt.tools import extract_ir_lib


def perform_build(source_dir, build_dir, corpus_dir, thread_count,
                  package_name):
  build_command_vector = [
      'swift', 'build', '-c', 'release', '-Xswiftc', '-embed-bitcode',
      '--emit-swift-module-separately', '-Xswiftc', '-Onone', '-j',
      str(thread_count), '--build-path', build_dir
  ]

  build_log_path = os.path.join(corpus_dir, 'build.log')

  try:
    with open(build_log_path, 'w') as build_log_file:
      subprocess.run(
          build_command_vector,
          cwd=source_dir,
          stdout=build_log_file,
          stderr=build_log_file,
          check=True)
  except subprocess.SubprocessError:
    logging.warning(f'Failed to build swift package in {package_name}')
    build_sucess = False
  else:
    build_sucess = True
  return {
      'success': build_sucess,
      'build_log': build_log_path,
      'name': package_name
  }


def extract_ir(build_dir, corpus_dir, threads):
  objects = extract_ir_lib.load_from_directory(build_dir, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(
      objects, threads, "llvm-objcopy", None, None, "__LLVM,__swift_cmdline",
      "__LLVM,__bitcode")
  extract_ir_lib.write_corpus_manifest(None, relative_output_paths, corpus_dir)

"""Module for building and extracting bitcode from applications using an
arbitrary build system by manually running specified commands."""

import subprocess
import os

from compiler_opt.tools import extract_ir_lib


def perform_build(commands_list, source_dir, threads, corpus_dir):
  for command in commands_list:
    environment = os.environ.copy()
    environment['JOBS'] = str(threads)
    build_config_file_path = os.path.join(corpus_dir, 'build.log')
    with open(build_config_file_path, 'w') as build_config_file:
      subprocess.run(
          command,
          cwd=source_dir,
          env=environment,
          shell=True,
          stderr=build_config_file,
          stdout=build_config_file)


def extract_ir(build_dir, corpus_dir, threads):
  objects = extract_ir_lib.load_from_directory(build_dir, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(objects, threads,
                                                        "llvm-objcopy", None,
                                                        None, ".llvmcmd",
                                                        ".llvmbc")
  extract_ir_lib.write_corpus_manifest(None, relative_output_paths, corpus_dir)

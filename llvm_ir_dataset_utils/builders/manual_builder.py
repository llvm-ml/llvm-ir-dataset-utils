"""Module for building and extracting bitcode from applications using an
arbitrary build system by manually running specified commands."""

import subprocess
import multiprocessing

from compiler_opt.tools import extract_ir_lib


def perform_build(commands_list, source_dir):
  for command in commands_list:
    subprocess.run(command, cwd=source_dir, shell=True)


def extract_ir(build_dir, corpus_dir):
  objects = extract_ir_lib.load_from_directory(build_dir, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(
      objects, multiprocessing.cpu_count(), "llvm-objcopy", None, None,
      ".llvmcmd", ".llvmbc")
  extract_ir_lib.write_corpus_manifest(None, relative_output_paths, corpus_dir)

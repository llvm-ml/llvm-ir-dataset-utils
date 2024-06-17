"""Module for building and extracting builder from a set of self-contained
C/c++ files."""

import subprocess
import os
import logging

from mlgo.corpus import extract_ir_lib
from mlgo.corpus import make_corpus_lib


def compile_file(source_file, object_file):
  command_vector = [
      'clang', '-Xclang', '-fembed-bitcode=all', '-c', source_file, '-o',
      object_file
  ]
  compile_process = subprocess.run(
      command_vector, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
  if compile_process.returncode != 0:
    logging.warning('Compiler returned non-zero exit code')


def perform_build(source_file_list, build_dir, corpus_dir):
  for source_file in source_file_list:
    object_file = os.path.join(build_dir, os.path.basename(source_file) + '.o')
    compile_file(source_file, object_file)

  return {
      'targets': [{
          'success': True,
          'build_log': None,
          'name': 'self_contained'
      }]
  }


# TODO(boomanaiden154): This is duplicated with extract_ir in the manual builder.
# We might want to look into refactoring to consolidate the two functions at some
# point.
def extract_ir(build_dir, corpus_dir, threads):
  objects = extract_ir_lib.load_from_directory(build_dir, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(objects, threads,
                                                        "llvm-objcopy", None,
                                                        None, ".llvmcmd",
                                                        ".llvmbc")
  extract_ir_lib.write_corpus_manifest(None, relative_output_paths, corpus_dir)

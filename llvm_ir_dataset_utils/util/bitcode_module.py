"""Utilities for working with bitcode modules."""

import subprocess
import os


def get_function_symbols(bitcode_module_path):
  # TODO(boomanaiden154): Adjust after symlinking to llvm-nm
  llvm_nm_command_vector = [
      'llvm-nm-16', '--export-symbols', bitcode_module_path
  ]
  llvm_nm_process = subprocess.run(
      llvm_nm_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      encoding='utf-8',
      check=True)
  return llvm_nm_process.stdout.split('\n')[:-1]


def extract_functions(bitcode_module_path, extraction_path):
  function_symbols_list = get_function_symbols(bitcode_module_path)
  for function_symbol in function_symbols_list:
    function_module_name = os.path.join(extraction_path,
                                        f'{function_symbol}.bc')
    # TODO(boomanaiden154): Adjust after symlinking to llvm-extract
    extract_command_vector = [
        'llvm-extract-16', '-func', function_symbol, bitcode_module_path, '-o',
        function_module_name
    ]
    subprocess.run(extract_command_vector, check=True)


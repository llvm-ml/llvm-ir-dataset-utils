"""Utilities for working with bitcode modules."""

import subprocess
import os
import tempfile
import logging


def get_function_symbols(bitcode_module_path):
  # TODO(boomanaiden154): Adjust after symlinking to llvm-nm
  llvm_nm_command_vector = [
      'llvm-nm-16', '--defined-only', '--format=posix', bitcode_module_path
  ]
  llvm_nm_process = subprocess.run(
      llvm_nm_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      encoding='utf-8',
      check=True)
  module_symbols = llvm_nm_process.stdout.split('\n')[:-1]
  module_list = []
  for symbol in module_symbols:
    symbol_parts = symbol.split(' ')
    # Only look for t or T symbols (actual code)
    if symbol_parts[1] == 't' or symbol_parts[1] == 'T':
      module_list.append(symbol_parts[0])
  return module_list


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
    extraction_process = subprocess.run(extract_command_vector)
    if extraction_process.returncode != 0:
      logging.info(
          f'Failed to extract {function_symbol} from {bitcode_module_path}')


def get_run_passes_opt(bitcode_function_path):
  opt_command_vector = [
      'opt', bitcode_function_path, '-print-changed', '-passes=default<O3>',
      '-o', '/dev/null'
  ]
  opt_process = subprocess.run(
      opt_command_vector,
      encoding='UTF-8',
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT)
  opt_process_lines = opt_process.stdout.split('\n')
  passes = []
  for opt_process_line in opt_process_lines:
    if opt_process_line[:3] == '***' and opt_process_line[-3:] == '***':
      # We're in a pass status line
      if opt_process_line[4:11] == 'IR Pass':
        # All module level passes are ignored, so we can't do anything here.
        continue
      if opt_process_line[-13:-4] == 'no change':
        passes.append(False)
      else:
        passes.append(True)
  return passes


def get_passes_bitcode_module(bitcode_module_path):
  with tempfile.TemporaryDirectory() as extracted_functions_dir:
    extract_functions(bitcode_module_path, extracted_functions_dir)
    function_bitcode_files = os.listdir(extracted_functions_dir)
    function_passes = []
    for function_bitcode_file in function_bitcode_files:
      full_bitcode_file_path = os.path.join(extracted_functions_dir,
                                            function_bitcode_file)
      function_passes.append(get_run_passes_opt(full_bitcode_file_path))
  return function_passes

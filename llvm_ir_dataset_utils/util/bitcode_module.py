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


def get_run_passes_opt(bitcode_function_path):
  opt_command_vector = [
      'opt', bitcode_function_path, '-print-changed', '-passes=default<O3>',
      '-o', '/dev/null'
  ]
  opt_process = subprocess.run(
      opt_command_vector,
      encoding='UTF-8',
      stdout=subprocess.DEVNULL,
      stderr=subprocess.PIPE,
      check=True)
  opt_process_lines = opt_process.stderr.split('\n')
  passes = []
  for opt_process_line in opt_process_lines:
    if opt_process_line[:3] == '***' and opt_process_line[-3:] == '***':
      # We're in a pass status line
      if opt_process_line[4:11] == 'IR Pass':
        # All module level passes are ignored, so we can't do anything here.
        continue
      if opt_process_line[-13:-4] == 'no change':
        passes.append((opt_process_line.split(' ')[4], False))
      else:
        passes.append((opt_process_line.split(' ')[4], True))
  return passes

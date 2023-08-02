"""Utilities for working with bitcode modules."""

import subprocess
import os
import tempfile
import logging


def get_function_symbols(bitcode_module):
  # TODO(boomanaiden154): Adjust after symlinking to llvm-nm
  llvm_nm_command_vector = [
      'llvm-nm-16', '--defined-only', '--format=posix', '-'
  ]
  with subprocess.Popen(
      llvm_nm_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      stdin=subprocess.PIPE) as llvm_nm_process:
    stdout = llvm_nm_process.communicate(
        input=bitcode_module)[0].decode('utf-8')
    if llvm_nm_process.returncode != 0:
      raise ValueError('Failed to get functions from bitcode module.')
    module_symbols = stdout.split('\n')[:-1]
  module_list = []
  for symbol in module_symbols:
    symbol_parts = symbol.split(' ')
    # Only look for t or T symbols (actual code)
    if symbol_parts[1] == 't' or symbol_parts[1] == 'T':
      module_list.append(symbol_parts[0])
  return module_list


def extract_functions(bitcode_module, extraction_path):
  function_symbols_list = get_function_symbols(bitcode_module)
  for function_symbol in function_symbols_list:
    function_module_name = os.path.join(extraction_path,
                                        f'{function_symbol}.bc')
    # TODO(boomanaiden154): Adjust after symlinking to llvm-extract
    extract_command_vector = [
        'llvm-extract-16', '-func', function_symbol, '-o', function_module_name
    ]
    with subprocess.Popen(
        extract_command_vector,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stdin=subprocess.PIPE) as extraction_process:
      extraction_process.communicate(input=bitcode_module)
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
  passes = {}
  for opt_process_line in opt_process_lines:
    if opt_process_line[:3] == '***' and opt_process_line[-3:] == '***':
      # We're in a pass status line
      if opt_process_line[4:11] == 'IR Pass':
        # Anything starting with IR Pass gets ignored, so we can't do anything
        # with it.
        continue
      if opt_process_line[12:20] == 'At Start':
        # Ignore the starting IR
        continue
      pass_name = opt_process_line.split(' on ')[0][12:]
      pass_name = pass_name.split('After ')[1]
      if opt_process_line[-13:-4] == 'no change':
        passes[pass_name] = [False]
      else:
        passes[pass_name] = [True]
  return passes


def combine_module_passes(function_a, function_b):
  if function_a is None or function_a == {}:
    return function_b
  combined_passes = function_a
  for single_pass in function_b:
    if single_pass in combined_passes:
      combined_passes[single_pass].extend(function_b[single_pass])
    else:
      combined_passes_length = len(combined_passes[list(
          combined_passes.keys())[0]])
      combined_passes[single_pass] = [
          False for i in range(0, combined_passes_length)
      ]
      combined_passes[single_pass].extend(function_b[single_pass])
  return combined_passes


def get_passes_bitcode_module(bitcode_module):
  with tempfile.TemporaryDirectory() as extracted_functions_dir:
    extract_functions(bitcode_module, extracted_functions_dir)
    function_bitcode_files = os.listdir(extracted_functions_dir)
    function_passes = {}
    for function_bitcode_file in function_bitcode_files:
      full_bitcode_file_path = os.path.join(extracted_functions_dir,
                                            function_bitcode_file)
      current_function_results = get_run_passes_opt(full_bitcode_file_path)
      function_passes = combine_module_passes(function_passes,
                                              current_function_results)
  return function_passes

"""Utilities for working with bitcode modules."""

import subprocess
import os
import tempfile
import logging

import ray

BITCODE_FILE_CHUNK_SIZE = 256


def get_function_symbols(bitcode_module):
  llvm_nm_command_vector = ['llvm-nm', '--defined-only', '--format=posix', '-']
  with subprocess.Popen(
      llvm_nm_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      stdin=subprocess.PIPE) as llvm_nm_process:
    stdout = llvm_nm_process.communicate(
        input=bitcode_module)[0].decode('utf-8')
    if llvm_nm_process.returncode != 0:
      logging.warning('Failed to get functions from bitcode module.')
      return []
    module_symbols = stdout.split('\n')[:-1]
  module_list = []
  for symbol in module_symbols:
    symbol_parts = symbol.split(' ')
    # Only look for t or T symbols (actual code)
    if symbol_parts[1] == 't' or symbol_parts[1] == 'T':
      module_list.append(symbol_parts[0])
  return module_list


def extract_individual_function(bitcode_module, extraction_path,
                                function_symbol):
  function_module_name = os.path.join(extraction_path, f'{function_symbol}.bc')
  extract_command_vector = [
      'llvm-extract', '-func', function_symbol, '-o', function_module_name
  ]
  with subprocess.Popen(
      extract_command_vector,
      stderr=subprocess.DEVNULL,
      stdout=subprocess.DEVNULL,
      stdin=subprocess.PIPE) as extraction_process:
    extraction_process.communicate(input=bitcode_module)
    if extraction_process.returncode != 0:
      logging.info(f'Failed to extract {function_symbol}')
      return []

  return [function_module_name]


def extract_functions(bitcode_module, extraction_path, function_symbols_list):
  extracted_functions = []
  for function_symbol in function_symbols_list:
    extracted_functions.extend(
        extract_individual_function(bitcode_module, extraction_path,
                                    function_symbol))
  return extracted_functions


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


def combine_module_statistics(function_a, function_b):
  if function_a is None or function_a == {}:
    return function_b
  combined_statistics = function_a
  for function_statistic in function_b:
    if function_statistic in combined_statistics:
      combined_statistics[function_statistic].extend(
          function_b[function_statistic])
    else:
      combined_statistics_length = len(combined_statistics[list(
          combined_statistics.keys())[0]])
      combined_statistics[function_statistic] = [
          False for i in range(0, combined_statistics_length)
      ]
      combined_statistics[function_statistic].extend(
          function_b[function_statistic])
  return combined_statistics


def get_function_properties(bitcode_function_path):
  properties_dict = {}
  opt_command_vector = [
      'opt', '-passes=print<func-properties>', bitcode_function_path, '-o',
      '/dev/null'
  ]
  opt_process = subprocess.run(
      opt_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      encoding='utf-8')
  if opt_process.returncode != 0:
    return {}
  output_lines = opt_process.stdout.split('\n')[1:-2]
  for output_line in output_lines:
    line_parts = output_line.split(': ')
    properties_dict[line_parts[0]] = [line_parts[1]]
  return properties_dict


@ray.remote(num_cpus=1)
def get_statistics_batch(bitcode_module, function_symbols, statistics_type):
  statistics = {}
  with tempfile.TemporaryDirectory() as extracted_functions_dir:
    bitcode_function_paths = extract_functions(bitcode_module,
                                               extracted_functions_dir,
                                               function_symbols)
    for bitcode_function_path in bitcode_function_paths:
      if statistics_type == 'properties':
        function_statistics = get_function_properties(bitcode_function_path)
      elif statistics_type == 'passes':
        function_statistics = get_run_passes_opt(bitcode_function_path)
      statistics = combine_module_statistics(statistics, function_statistics)
  return statistics


# TODO(boomanaiden154): Probably put this into a separate parallel util module
# or something.
# TODO(boomanaiden154): Write some unit tests for this function.
def split_batches(individual_jobs, batch_size):
  batches = []
  current_start_index = 0
  while True:
    end_index = current_start_index + batch_size
    chunk = individual_jobs[current_start_index:end_index]
    batches.append(chunk)
    current_start_index = end_index
    if current_start_index + batch_size >= len(individual_jobs):
      last_chunk = individual_jobs[current_start_index:]
      batches.append(last_chunk)
      break
  return batches


def get_bitcode_module_statistics(bitcode_module, statistics_type):
  with tempfile.TemporaryDirectory() as extracted_functions_dir:
    function_symbols = get_function_symbols(bitcode_module)

    statistics_futures = []
    batches = split_batches(function_symbols, BITCODE_FILE_CHUNK_SIZE)
    for batch in batches:
      statistics_futures.append(
          get_statistics_batch.remote(bitcode_module, batch, statistics_type))

    statistics_chunks = ray.get(statistics_futures)
    statistics = {}
    for statistics_chunk in statistics_chunks:
      statistics = combine_module_statistics(statistics, statistics_chunk)
  return statistics

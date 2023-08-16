"""Utilities for working with bitcode modules."""

import subprocess
import os
import tempfile
import logging
import json

import ray

from llvm_ir_dataset_utils.util import dataset_corpus
from llvm_ir_dataset_utils.util import pass_list_constants
from llvm_ir_dataset_utils.util import parallel

BITCODE_FILE_CHUNK_SIZE = 256

OPT_TIMEOUT_SECONDS = 60


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
      return (stdout.replace('\n', ''), None)
    module_symbols = stdout.split('\n')[:-1]
  module_list = []
  for symbol in module_symbols:
    symbol_parts = symbol.split(' ')
    # Only look for t or T symbols (actual code)
    if symbol_parts[1] == 't' or symbol_parts[1] == 'T':
      module_list.append(symbol_parts[0])
  return (None, module_list)


def extract_individual_function(bitcode_module, extraction_path,
                                function_symbol):
  function_module_name = os.path.join(extraction_path, f'{function_symbol}.bc')
  extract_command_vector = [
      'llvm-extract', '-func', function_symbol, '-o', function_module_name
  ]
  with subprocess.Popen(
      extract_command_vector,
      stderr=subprocess.STDOUT,
      stdout=subprocess.PIPE,
      stdin=subprocess.PIPE) as extraction_process:
    stdout = extraction_process.communicate(
        input=bitcode_module)[0].decode('utf-8')
    if extraction_process.returncode != 0:
      logging.info(f'Failed to extract {function_symbol}')
      return (stdout.replace('\n', ''), None)

  return (None, function_module_name)


def get_run_passes_opt(bitcode_function_path):
  opt_command_vector = [
      'opt', bitcode_function_path, '-print-changed', '-passes=default<O3>',
      '-o', '/dev/null'
  ]
  try:
    opt_process = subprocess.run(
        opt_command_vector,
        encoding='UTF-8',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=OPT_TIMEOUT_SECONDS)
  except:
    return ('timeout', None)
  if opt_process.returncode != 0:
    return (opt_process.stdout.replace('\n', ''), None)
  opt_process_lines = opt_process.stdout.split('\n')
  pass_indexes = {}
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
      ir_changed = opt_process_line[-13:-4] == 'no change'
      # Special case loop passes because they run once per loop rather than
      # once per function.
      if pass_name in pass_list_constants.LOOP_PASS_LIST:
        pass_name = pass_name + '1'
        if pass_name not in passes or not passes[pass_name]:
          passes[pass_name] = ir_changed
      elif pass_name in pass_indexes:
        pass_indexes[pass_name] += 1
        pass_name = f'{pass_name}{pass_indexes[pass_name]}'
      else:
        pass_indexes[pass_name] = 1
        pass_name = pass_name + '1'
      if ir_changed:
        passes[pass_name] = [False]
      else:
        passes[pass_name] = [True]
  return (None, passes)


def combine_statistics(function_a, function_b, fill_value=False):
  if function_a is None or function_a == {}:
    return function_b
  combined_statistics = function_a
  combined_statistics_length = len(combined_statistics[list(
      combined_statistics.keys())[0]])
  for function_statistic in list(
      set(list(function_a.keys()) + list(function_b.keys()))):
    if function_statistic in combined_statistics and function_statistic in function_b:
      combined_statistics[function_statistic].extend(
          function_b[function_statistic])
    elif function_statistic in function_b:
      combined_statistics[function_statistic] = [
          fill_value for i in range(0, combined_statistics_length)
      ]
      combined_statistics[function_statistic].extend(
          function_b[function_statistic])
    elif function_statistic in combined_statistics:
      function_b_statistics_length = len(function_b[list(function_b.keys())[0]])
      extra_values = [
          fill_value for i in range(0, function_b_statistics_length)
      ]
      combined_statistics[function_statistic].extend(extra_values)
  return combined_statistics


def get_function_properties(bitcode_function_path,
                            passes="print<func-properties>"):
  properties_dict = {}
  opt_command_vector = [
      'opt', f'-passes={passes}', bitcode_function_path, '-o', '/dev/null'
  ]
  try:
    opt_process = subprocess.run(
        opt_command_vector,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8',
        timeout=OPT_TIMEOUT_SECONDS)
  except SubprocessError:
    return ('timeout', None)
  if opt_process.returncode != 0:
    return (opt_process.stdout.replace('\n', ''), None)
  output_lines = opt_process.stdout.split('\n')[1:-2]
  for output_line in output_lines:
    line_parts = output_line.split(': ')
    properties_dict[line_parts[0]] = [line_parts[1]]
  return (None, properties_dict)


def parse_bcanalyzer_output(output_string):
  distribution_dict = {}
  output_lines = output_string.split('\n')
  line_index = 0
  while line_index < len(output_lines):
    output_line = output_lines[line_index]
    line_index += 1
    output_line_parts = output_line.split()
    if '(FUNCTION_BLOCK):' in output_line:
      # Grab the actual data
      line_index += 12
      while not output_lines[line_index].isspace(
      ) and output_lines[line_index] != '':
        histogram_parts = output_lines[line_index].split()
        distribution_dict[histogram_parts[-1]] = [int(histogram_parts[0])]
        line_index += 1
      break
  return distribution_dict


def get_instruction_distribution_path(bitcode_function_path):
  bcanalyzer_command_vector = ['llvm-bcanalyzer', bitcode_function_path]
  analyzer_process = subprocess.run(
      bcanalyzer_command_vector, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  properties_dict = parse_bcanalyzer_output(
      analyzer_process.stdout.decode('utf-8'))
  return (None, properties_dict)


@ray.remote(num_cpus=1)
def get_function_statistics_batch(bitcode_module, function_symbols,
                                  statistics_type, module_path):
  statistics = []
  with tempfile.TemporaryDirectory() as extracted_functions_dir:
    for function_symbol in function_symbols:
      expected_extracted_function_path = extract_individual_function(
          bitcode_module, extracted_functions_dir, function_symbol)
      function_path = f'{module_path}:{function_symbol}'
      if expected_extracted_function_path[0]:
        statistics.append(
            (expected_extracted_function_path[0], None, function_path))
        continue
      bitcode_function_path = expected_extracted_function_path[1]
      if statistics_type == 'properties':
        function_statistics_expected = get_function_properties(
            bitcode_function_path)
      elif statistics_type == 'passes':
        function_statistics_expected = get_run_passes_opt(bitcode_function_path)
      elif statistics_type == 'post_opt_properties':
        function_statistics_expected = get_function_properties(
            bitcode_function_path, 'default<O3>,print<func-properties>')
      elif statistics_type == 'instruction_distribution':
        function_statistics_expected = get_instruction_distribution_path(
            bitcode_function_path)
      if function_statistics_expected[0]:
        statistics.append(
            (function_statistics_expected[0], None, function_path))
      else:
        statistics.append(
            (None, function_statistics_expected[1], function_path))
  return statistics


def get_bitcode_module_function_statistics(bitcode_module, statistics_type,
                                           module_path):
  with tempfile.TemporaryDirectory() as extracted_functions_dir:
    function_symbols_expected = get_function_symbols(bitcode_module)

    if function_symbols_expected[0]:
      return [(function_symbols_expected[0], None, module_path)]

    function_symbols = function_symbols_expected[1]

    statistics_futures = []
    batches = parallel.split_batches(function_symbols, BITCODE_FILE_CHUNK_SIZE)
    for batch in batches:
      statistics_futures.append(
          get_function_statistics_batch.remote(bitcode_module, batch,
                                               statistics_type, module_path))

    statistics_chunks = ray.get(statistics_futures)
    statistics = []
    for statistics_chunk in statistics_chunks:
      statistics.extend(statistics_chunk)
  return statistics


def test_parsing(bitcode_module):
  opt_command_vector = ['opt', '-', '-o', '/dev/null']
  with subprocess.Popen(
      opt_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      stdin=subprocess.PIPE) as opt_process:
    stdout = opt_process.communicate(
        input=bitcode_module, timeout=OPT_TIMEOUT_SECONDS)[0].decode('utf-8')
    return (stdout.replace('\n', ''), {
        'parseable': [opt_process.returncode == 0]
    })


def get_size(bitcode_module):
  return (None, {'size': [len(bitcode_module)]})


@ray.remote(num_cpus=1)
def get_module_statistics_batch(project_dir, module_paths, statistics_type):
  statistics = []
  for module_path in module_paths:
    bitcode_file = dataset_corpus.load_file_from_corpus(project_dir,
                                                        module_path)
    if statistics_type == 'parsing':
      parse_result = test_parsing(bitcode_file)
      if parse_result[1] == True:
        statistics.append((None, parse_result[1], module_path))
      else:
        statistics.append((parse_result[0], parse_result[1], module_path))
    if statistics_type == 'module_size':
      statistics.append((None, get_size(bitcode_file)[1], module_path))
  return statistics


def get_tokenization(bitcode_module):
  tokenizer_command_vector = ['llvm-tokenizer', '-output-mode=json', '-']
  with subprocess.Popen(
      tokenizer_command_vector,
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE) as tokenizer_process:
    try:
      stdout = tokenizer_process.communicate(input=bitcode_module)[0]
      return json.loads(stdout)
    except json.JSONDecodeError:
      # TODO(boomanaiden154): This is failing pretty often. Get more debug
      # information (like file path) into these logs so we can do downstream
      # analysis.
      logging.warning('Failed to decode JSON')
      return {}

#!/usr/bin/env python3
"""Run Clang and retain the source inputs of successful compilations."""

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass

SOURCE_FILE_EXTENSIONS = {
    '.c', '.cc', '.cp', '.cpp', '.cxx', '.c++', '.i', '.ii'
}
C_AND_CXX_LANGUAGES = {
    'c', 'c-header', 'cpp-output', 'c++', 'c++-header', 'c++-cpp-output'
}

# Options whose following argument is not a compiler input. Joined forms such
# as -Ifoo do not need special handling because they begin with a dash.
OPTIONS_WITH_VALUE = {
    '-arch', '-B', '-D', '-gcc-toolchain', '-I', '-idirafter', '-iframework',
    '-imacros', '-include', '-iquote', '-isystem', '-isysroot', '-L', '-l',
    '-mllvm', '-MF', '-MJ', '-MQ', '-MT', '-o', '-resource-dir', '-target',
    '-U', '-Xassembler', '-Xclang', '-Xlinker', '-Xpreprocessor', '--sysroot',
    '--gcc-toolchain', '--target'
}

DEPENDENCY_OPTIONS = {'-M', '-MD', '-MG', '-MM', '-MMD', '-MP'}
DEPENDENCY_OPTIONS_WITH_VALUE = {'-MF', '-MJ', '-MQ', '-MT'}


@dataclass(frozen=True)
class ParsedInvocation:
  output_file: str
  source_files: tuple
  source_indices: tuple
  mode: str
  expanded_arguments: tuple


def _compiler_for_mode(mode):
  return 'clang++' if mode == 'c++' else 'clang'


def _compiler_mode(program):
  return 'c++' if os.path.basename(program).endswith('++') else 'c'


def run_compiler_invocation(mode, compiler_arguments):
  command_vector = [_compiler_for_mode(mode), *compiler_arguments]
  return subprocess.run(command_vector).returncode


def _expand_response_files(arguments, response_stack=()):
  """Expand Clang-style response files for inspection and preprocessing."""
  expanded = []
  for argument in arguments:
    if not argument.startswith('@') or len(argument) == 1:
      expanded.append(argument)
      continue

    response_path = os.path.abspath(argument[1:])
    if response_path in response_stack:
      raise ValueError(f'recursive response file: {argument[1:]}')

    with open(response_path, encoding='utf-8') as response_file:
      response_arguments = shlex.split(
          response_file.read(), comments=False, posix=True)
    expanded.extend(
        _expand_response_files(response_arguments,
                               (*response_stack, response_path)))
  return expanded


def _output_file(arguments):
  output_file = None
  index = 0
  while index < len(arguments):
    argument = arguments[index]
    if argument == '-o':
      if index + 1 >= len(arguments):
        return None
      output_file = arguments[index + 1]
      index += 2
      continue
    if argument.startswith('-o') and len(argument) > 2:
      output_file = argument[2:]
    index += 1
  return output_file


def _source_inputs(arguments):
  sources = []
  source_indices = []
  language = None
  index = 0

  while index < len(arguments):
    argument = arguments[index]
    if argument == '-x':
      if index + 1 >= len(arguments):
        break
      language = arguments[index + 1]
      index += 2
      continue
    if argument.startswith('-x') and len(argument) > 2:
      language = argument[2:]
      index += 1
      continue
    if argument in OPTIONS_WITH_VALUE:
      index += 2
      continue
    if argument.startswith('-'):
      index += 1
      continue

    extension = os.path.splitext(argument)[1].lower()
    explicit_source = language in C_AND_CXX_LANGUAGES
    if extension in SOURCE_FILE_EXTENSIONS or explicit_source:
      sources.append(argument)
      source_indices.append(index)
    index += 1

  return sources, source_indices


def parse_args(arguments):
  mode = _compiler_mode(arguments[0])
  try:
    expanded_arguments = _expand_response_files(arguments[1:])
  except (OSError, ValueError) as error:
    _warn(f'cannot inspect compiler arguments: {error}')
    return None

  output_file = _output_file(expanded_arguments)
  source_files, source_indices = _source_inputs(expanded_arguments)
  if output_file is None or not source_files:
    return None

  return ParsedInvocation(output_file,
                          tuple(source_files), tuple(source_indices), mode,
                          tuple(expanded_arguments))


def _artifact_paths(output_file, source_count, source_index):
  if source_count == 1:
    prefix = output_file
  else:
    prefix = f'{output_file}.{source_index}'
  return prefix + '.source', prefix + '.preprocessed_source'


def _preprocessor_arguments(invocation, selected_source_index, output_path):
  arguments = list(invocation.expanded_arguments)
  source_indices = set(invocation.source_indices)
  filtered = []
  index = 0

  while index < len(arguments):
    argument = arguments[index]
    if index in source_indices and index != selected_source_index:
      index += 1
      continue
    if argument in DEPENDENCY_OPTIONS:
      index += 1
      continue
    if argument in DEPENDENCY_OPTIONS_WITH_VALUE:
      index += 2
      continue
    if any(
        argument.startswith(option) and len(argument) > len(option)
        for option in DEPENDENCY_OPTIONS_WITH_VALUE):
      index += 1
      continue
    if argument == '-o':
      filtered.extend(('-o', output_path))
      index += 2
      continue
    if argument.startswith('-o') and len(argument) > 2:
      filtered.append('-o' + output_path)
      index += 1
      continue
    filtered.append(argument)
    index += 1

  # -w ensures linker-only options retained from a compile-and-link invocation
  # cannot turn preprocessing diagnostics into a failure under -Werror.
  filtered.extend(('-E', '-w'))
  return filtered


def _warn(message):
  print(f'compiler_wrapper: {message}', file=sys.stderr)


def _remove_incomplete_artifact(path):
  try:
    os.remove(path)
  except FileNotFoundError:
    pass
  except OSError as error:
    _warn(f'cannot remove incomplete output {path!r}: {error}')


def save_sources(invocation):
  for artifact_index, (source_file, source_argument_index) in enumerate(
      zip(invocation.source_files, invocation.source_indices)):
    source_path, preprocessed_path = _artifact_paths(
        invocation.output_file, len(invocation.source_files), artifact_index)
    try:
      shutil.copyfile(source_file, source_path)
    except OSError as error:
      _warn(f'cannot save source {source_file!r}: {error}')
      _remove_incomplete_artifact(source_path)

    preprocess_arguments = _preprocessor_arguments(invocation,
                                                   source_argument_index,
                                                   preprocessed_path)
    try:
      preprocess_result = run_compiler_invocation(invocation.mode,
                                                  preprocess_arguments)
    except OSError as error:
      _warn(f'cannot preprocess {source_file!r}: {error}')
      _remove_incomplete_artifact(preprocessed_path)
      continue
    if preprocess_result != 0:
      _warn(
          f'failed to preprocess {source_file!r} (exit code {preprocess_result})'
      )
      _remove_incomplete_artifact(preprocessed_path)


def main(args):
  mode = _compiler_mode(args[0])
  invocation = parse_args(args)
  return_code = run_compiler_invocation(mode, args[1:])
  if return_code == 0 and invocation is not None:
    save_sources(invocation)
  sys.exit(return_code)


if __name__ == '__main__':
  main(sys.argv)

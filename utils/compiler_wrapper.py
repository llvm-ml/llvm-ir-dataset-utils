#!/bin/python
"""This script wraps the compiler, taking in the compiler options and saving
the source files that are used within the compilation step."""

import os
import subprocess
import sys

RECOGNIZED_SOURCE_FILE_EXTENSIONS = ['.c', 'cpp', '.cxx', '.cc']


def run_compiler_invocation(mode, compiler_arguments):
  command_vector = []

  if mode == 'c++':
    command_vector.append('clang++')
  else:
    command_vector.append('clang')

  command_vector.extend(compiler_arguments)

  subprocess.run(command_vector)


def save_source(source_files, output_file):
  # TODO(boomanaiden154): Flesh this function out
  for source_file in source_files:
    print(f'saving {source_file}')


def parse_args(arguments_split):
  output_file_path = None
  try:
    output_arg_index = arguments_split.index('-o') + 1
    output_file_path = arguments_split[output_arg_index]
  except:
    return None

  input_files = []

  for argument in arguments_split:
    for recognized_extension in RECOGNIZED_SOURCE_FILE_EXTENSIONS:
      if argument.endswith(recognized_extension):
        input_files.append(argument)

  mode = 'c++'
  if not arguments_split[0].endswith('++'):
    mode = 'c'

  return (output_file_path, input_files, mode)


def main(args):
  parsed_arguments = parse_args(args)
  if not parsed_arguments:
    # We couldn't parse the arguments. This could be for a varietey of reasons.
    # In this case, don't copy over any files and just run the compiler
    # invocation.
    run_compiler_invocation(args[1:])

  output_file_path, input_files, mode = parsed_arguments

  save_source(input_files, output_file_path)

  run_compiler_invocation(mode, args[1:])


if __name__ == '__main__':
  main(sys.argv)

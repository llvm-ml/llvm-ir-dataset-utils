"""Tool for taking in a list of module hashes and extracting all deduplicated
modules into a separate directory."""

import os
import logging
import csv

from absl import flags
from absl import app

import llvm_ir_dataset_utils.util.dataset_corpus

FLAGS = flags.FLAGS

flags.DEFINE_string('module_hash_list', None,
                    'A list of module hashes to pull from.')
flags.DEFINE_string(
    'output_path', None,
    'The output path to place all the deduplicated modules into.')

flags.mark_flag_as_required('module_hash_list')
flags.mark_flag_as_required('output_path')


def load_module_hashes(file_path):
  module_hash_map = {}
  with open(file_path) as module_hashes_file:
    module_hash_reader = csv.DictReader(module_hashes_file)
    for module_hash_entry in module_hash_reader:
      module_hash = module_hash_entry['module_hashes']
      file_path = module_hash_entry['name']
      # Skip empty modules which get hashes to the default value of 4
      if module_hash == '4':
        continue
      module_hash_map[module_hash] = file_path
  return module_hash_map


def extract_files_from_hash_map(module_hash_map, output_path):
  for module_hash in module_hash_map:
    file_path_full = module_hash_map[module_hash]
    file_path_parts = file_path_full.split(':')
    bitcode_file = llvm_ir_dataset_utils.util.dataset_corpus.load_file_from_corpus(
        file_path_parts[0], file_path_parts[1])
    with open(os.path.join(output_path, f'{module_hash}.bc'),
              'wb') as bitcode_file_handle:
      bitcode_file_handle.write(bitcode_file)


def main(_):
  module_hash_map = load_module_hashes(FLAGS.module_hash_list)
  extract_files_from_hash_map(module_hash_map, FLAGS.output_path)


if __name__ == '__main__':
  app.run(main)

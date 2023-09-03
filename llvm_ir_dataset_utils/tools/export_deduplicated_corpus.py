"""Tool for taking in a list of module hashes and extracting all deduplicated
modules into a separate directory."""

import os
import logging
import csv
import shutil
import json

from absl import flags
from absl import app

import ray

from llvm_ir_dataset_utils.util import dataset_corpus
from llvm_ir_dataset_utils.util import parallel

FLAGS = flags.FLAGS

flags.DEFINE_multi_string('module_hash_list', None,
                          'A list of module hashes to pull from.')
flags.DEFINE_string(
    'output_path', None,
    'The output path to place all the deduplicated modules into.')
flags.DEFINE_integer('batch_size', 256,
                     'The number of modules to put in each batch.')

flags.mark_flag_as_required('module_hash_list')
flags.mark_flag_as_required('output_path')


def load_module_hashes(file_path):
  logging.info(f'Loading data from {file_path}')
  module_hash_map = {}
  all_modules_count = 0
  with open(file_path) as module_hashes_file:
    module_hash_reader = csv.DictReader(module_hashes_file)
    for module_hash_entry in module_hash_reader:
      all_modules_count += 1
      module_hash = module_hash_entry['module_hashes']
      file_path = module_hash_entry['name']
      # Skip empty modules which get hashes to the default value of 4
      if module_hash == '4':
        continue
      module_hash_map[module_hash] = file_path
  logging.info(f'Read {all_modules_count} modules.')
  logging.info(f'Found {len(module_hash_map)} unique modules.')
  return module_hash_map


def create_manifest(file_path, modules_list):
  corpus_description = {'has_thinlto': False, 'modules': []}
  for module_tuple in modules_list:
    # Omit the .bc file extension because it gets added on by different
    # tooling.
    corpus_description['modules'].append(f'{module_tuple[1]}')
  with open(file_path, 'w') as corpus_description_file:
    json.dump(corpus_description, corpus_description_file, indent=2)


@ray.remote(num_cpus=1)
def process_module_batch(batch_path, modules_to_process):
  os.mkdir(batch_path)
  for module_path in modules_to_process:
    file_path_full = module_path[0]
    module_hash = module_path[1]
    file_path_parts = file_path_full.split(':')
    bitcode_file = dataset_corpus.load_file_from_corpus(file_path_parts[0],
                                                        file_path_parts[1])
    with open(os.path.join(batch_path, f'{module_hash}.bc'),
              'wb') as bitcode_file_handle:
      bitcode_file_handle.write(bitcode_file)
    # Process the .cmd file
    command_line_file_path = file_path_parts[1][:-3] + '.cmd'
    command_line_data = ''
    if dataset_corpus.is_file_in_corpus(file_path_parts[0],
                                        command_line_file_path):
      command_line_data = dataset_corpus.load_file_from_corpus(
          file_path_parts[0], command_line_file_path).decode('utf-8')
    else:
      command_line_data = ''
    with open(os.path.join(batch_path, f'{module_hash}.cmd'),
              'w') as command_line_file_handle:
      command_line_file_handle.write(command_line_data)

  create_manifest(
      os.path.join(batch_path, 'corpus_description.json'), modules_to_process)
  shutil.make_archive(batch_path, 'tar', batch_path)
  shutil.rmtree(batch_path)


def extract_files_from_hash_map(module_hash_map, output_path):
  modules_to_process = []

  for module_hash in module_hash_map:
    # format is (path, hash)
    modules_to_process.append((module_hash_map[module_hash], module_hash))

  module_batches = parallel.split_batches(modules_to_process, FLAGS.batch_size)

  module_batch_futures = []

  for index, module_batch in enumerate(module_batches):
    batch_path = os.path.join(FLAGS.output_path, f'batch-{index}')
    module_batch_futures.append(
        process_module_batch.remote(batch_path, module_batch))

  while len(module_batch_futures) > 0:
    finished, module_batch_futures = ray.wait(module_batch_futures, timeout=5.0)
    finished_data = ray.get(finished)
    logging.info(
        f'Just finished {len(finished_data)}, {len(module_batch_futures)} remaining.'
    )


def main(_):
  ray.init()

  module_hash_map = {}

  for module_hash_list_path in FLAGS.module_hash_list:
    module_hash_map.update(load_module_hashes(module_hash_list_path))

  extract_files_from_hash_map(module_hash_map, FLAGS.output_path)


if __name__ == '__main__':
  app.run(main)

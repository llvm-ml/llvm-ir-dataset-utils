"""Tool for taking in a list of module hashes and extracting all deduplicated
modules into a separate directory."""

import os
import logging
import csv
import shutil

from absl import flags
from absl import app

import ray

from llvm_ir_dataset_utils.util import dataset_corpus
from llvm_ir_dataset_utils.util import parallel

FLAGS = flags.FLAGS

flags.DEFINE_string('module_hash_list', None,
                    'A list of module hashes to pull from.')
flags.DEFINE_string(
    'output_path', None,
    'The output path to place all the deduplicated modules into.')
flags.DEFINE_integer('batch_size', 256,
                     'The number of modules to put in each batch.')

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

  module_hash_map = load_module_hashes(FLAGS.module_hash_list)
  extract_files_from_hash_map(module_hash_map, FLAGS.output_path)


if __name__ == '__main__':
  app.run(main)

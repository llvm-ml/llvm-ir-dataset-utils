"""Tool for getting statistics on bitcode modules."""

import os
import glob
import logging
import csv

from absl import app
from absl import flags

import ray

from llvm_ir_dataset_utils.util import bitcode_module
from llvm_ir_dataset_utils.util import dataset_corpus

FLAGS = flags.FLAGS

# TODO(boomanaiden154): Refactor this to a corpus directory, maybe with a sampling/filtering
# clause to allow for smaller scale testing.
flags.DEFINE_string('corpus_dir', None,
                    'The corpus directory to look for modules in.')
flags.DEFINE_string('output_file_path', None, 'The output file.')

flags.mark_flag_as_required('corpus_dir')
flags.mark_flag_as_required('output_file_path')


@ray.remote
def process_single_project(project_dir):
  passes_changed = {}
  bitcode_modules = dataset_corpus.get_bitcode_file_paths(project_dir)
  for bitcode_file_path in bitcode_modules:
    bitcode_file = dataset_corpus.load_file_from_corpus(project_dir,
                                                        bitcode_file_path)
    modules_passes_ran = bitcode_module.get_passes_bitcode_module(bitcode_file)
    passes_changed = bitcode_module.combine_module_passes(
        passes_changed, modules_passes_ran)
  return passes_changed


def main(_):
  ray.init()

  projects = os.listdir(FLAGS.corpus_dir)
  project_futures = []

  for project_dir in projects:
    full_project_path = os.path.join(FLAGS.corpus_dir, project_dir)
    project_futures.append(process_single_project.remote(full_project_path))

  passes_changed = {}

  while len(project_futures) > 0:
    finished, project_futures = ray.wait(project_futures, timeout=5.0)
    logging.info(
        f'Just finished {len(finished)}, {len(project_futures)} remaining.')
    for change_info in ray.get(finished):
      passes_changed = bitcode_module.combine_module_passes(
          passes_changed, change_info)

  with open(FLAGS.output_file_path, 'w') as output_file:
    csv_writer = csv.writer(output_file)
    csv_writer.writerow(passes_changed.keys())
    csv_writer.writerows(zip(*passes_changed.values()))


if __name__ == '__main__':
  app.run(main)

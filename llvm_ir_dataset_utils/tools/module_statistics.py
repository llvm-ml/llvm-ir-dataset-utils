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
flags.DEFINE_enum('type', 'properties', ['properties', 'passes'],
                  'The type of statistics to collect.')

flags.mark_flag_as_required('corpus_dir')
flags.mark_flag_as_required('output_file_path')


@ray.remote(num_cpus=1)
def process_single_project(project_dir, statistics_type):
  statistics = {}
  bitcode_modules = dataset_corpus.get_bitcode_file_paths(project_dir)
  for bitcode_file_path in bitcode_modules:
    bitcode_file = dataset_corpus.load_file_from_corpus(project_dir,
                                                        bitcode_file_path)
    module_statistics = bitcode_module.get_bitcode_module_statistics(
        bitcode_file, statistics_type)
    statistics = bitcode_module.combine_module_statistics(
        statistics, module_statistics)
  return statistics


def collect_statistics(projects_list, statistics_type):
  project_futures = []

  for project_dir in projects_list:
    full_project_path = os.path.join(FLAGS.corpus_dir, project_dir)
    project_futures.append(
        process_single_project.remote(full_project_path, statistics_type))

  statistics = {}

  while len(project_futures) > 0:
    finished, project_futures = ray.wait(project_futures, timeout=5.0)
    logging.info(
        f'Just finished {len(finished)}, {len(project_futures)} remaining.')
    for project_statistics in ray.get(finished):
      statistics = bitcode_module.combine_module_statistics(
          statistics, project_statistics)

  with open(FLAGS.output_file_path, 'w') as output_file:
    csv_writer = csv.writer(output_file)
    csv_writer.writerow(statistics.keys())
    csv_writer.writerows(zip(*statistics.values()))


def main(_):
  ray.init()

  projects = os.listdir(FLAGS.corpus_dir)

  collect_statistics(projects, FLAGS.type)


if __name__ == '__main__':
  app.run(main)

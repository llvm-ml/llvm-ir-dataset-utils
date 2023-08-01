"""Tool for getting statistics on bitcode modules."""

import os
import glob
import logging
import csv

from absl import app
from absl import flags

from llvm_ir_dataset_utils.util import bitcode_module

FLAGS = flags.FLAGS

# TODO(boomanaiden154): Refactor this to a corpus directory, maybe with a sampling/filtering
# clause to allow for smaller scale testing.
flags.DEFINE_string('project_dir', None,
                    'The corpus directory to look for modules in.')
flags.DEFINE_string('output_file_path', None, 'The output file.')

flags.mark_flag_as_required('project_dir')
flags.mark_flag_as_required('output_file_path')


def main(_):
  passes_changed = {}
  for bitcode_file_path in glob.glob(
      os.path.join(FLAGS.project_dir, '**/*.bc'), recursive=True):
    bitcode_file_full_path = os.path.join(FLAGS.project_dir, bitcode_file_path)
    logging.info(f'processing {bitcode_file_full_path}')
    modules_passes_ran = bitcode_module.get_passes_bitcode_module(
        bitcode_file_full_path)
    passes_changed = bitcode_module.combine_module_passes(
        passes_changed, modules_passes_ran)

  with open(FLAGS.output_file_path, 'w') as output_file:
    csv_writer = csv.writer(output_file)
    csv_writer.writerow(passes_changed.keys())
    csv_writer.writerows(zip(*passes_changed.values()))


if __name__ == '__main__':
  app.run(main)

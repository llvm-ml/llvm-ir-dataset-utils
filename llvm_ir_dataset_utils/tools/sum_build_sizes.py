"""Tool for summing the size information from module_statistics.py"""

import os
import logging

from absl import app
from absl import flags

FLAGS = flags.FLAGS

flags.DEFINE_string('input_path', None,
                    'The CSV file containing the size information')

flags.mark_flag_as_required('input_path')


def main(_):
  logging.info('Loading CSV file')
  file_sizes = []
  with open(FLAGS.input_path) as input_file_handle:
    # Skip the first line which contains header information
    next(input_file_handle)
    for line in input_file_handle:
      file_sizes.append(int(line.split(',')[0]))

  logging.info('Summing information')

  size_sum = sum(file_sizes)

  logging.info(f'The total size is {size_sum}')


if __name__ == '__main__':
  app.run(main)

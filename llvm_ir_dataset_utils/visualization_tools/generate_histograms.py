"""A tool for generating histograms from a CSV file."""

import logging
import os

import pandas
import matplotlib.pyplot

from absl import app
from absl import flags

FLAGS = flags.FLAGS

flags.DEFINE_string('data_path', None, 'The path to the data file.')
flags.DEFINE_string('output_path', None,
                    'The path to a folder to write the histograms to.')
flags.DEFINE_integer('num_bins', 20,
                     'The number of bins to use for the histograms.')

flags.mark_flag_as_required('data_path')
flags.mark_flag_as_required('output_path')


def main(_):
  logging.info('Loading data.')
  data_frame = pandas.read_csv(FLAGS.data_path)

  for column in data_frame:
    print(column)

  logging.info('Finished loading data, generating histograms.')

  for column in data_frame:
    matplotlib.pyplot.hist(
        data_frame[column].to_numpy(), bins=FLAGS.num_bins, log=True)
    matplotlib.pyplot.savefig(os.path.join(FLAGS.output_path, f'{column}.png'))
    matplotlib.pyplot.close()


if __name__ == '__main__':
  app.run(main)

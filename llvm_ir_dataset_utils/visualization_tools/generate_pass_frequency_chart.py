"""A tool for generating bar charts describing how often passes run using a
bar chart.
"""

import logging

import pandas
import matplotlib.pyplot

from absl import app
from absl import flags

from llvm_ir_dataset_utils.util import pass_list_constants

FLAGS = flags.FLAGS

flags.DEFINE_string('data_path', None, 'The path to the data file.')
flags.DEFINE_string('output_file', None,
                    'The path to place the output image at.')
flags.DEFINE_bool('log_scale', False,
                  'Whether or not to generate chart with a log scale.')

flags.mark_flag_as_required('data_path')
flags.mark_flag_as_required('output_file')


def main(_):
  logging.info('Loading data.')
  data_frame = pandas.read_csv(FLAGS.data_path)
  data_frame.drop(['name'], axis=1, inplace=True)
  data_frame = data_frame[pass_list_constants.OPT_DEFAULT_O3_PASS_LIST]

  labels = []
  percentages = []

  for column in data_frame.keys():
    labels.append(column)
    percentages.append(data_frame[column].sum() / data_frame.shape[0])

  logging.info('Finished loading data, generating figures.')

  matplotlib.pyplot.figure(figsize=(10, 10))
  matplotlib.pyplot.bar(labels, percentages, log=FLAGS.log_scale)
  matplotlib.pyplot.xticks(rotation=90)
  matplotlib.pyplot.tight_layout()
  matplotlib.pyplot.savefig(FLAGS.output_file)
  matplotlib.pyplot.close()


if __name__ == '__main__':
  app.run(main)

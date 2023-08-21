"""A tool for generating bar charts describing how often passes run using a
bar chart.
"""

import logging

import pandas
import plotly.express

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

  # Only grab passes that we have in case we only have a sample that misses
  # some of the loop passes. We're only transforming everything to make sure
  # it's all in order.
  passes_to_grab = []
  for pass_name in pass_list_constants.OPT_DEFAULT_O3_PASS_LIST:
    if pass_name in data_frame.columns:
      passes_to_grab.append(pass_name)

  data_frame = data_frame[passes_to_grab]

  labels = []
  percentages = []

  for column in data_frame.keys():
    labels.append(column)
    percentages.append(data_frame[column].sum() / data_frame.shape[0])

  final_data = pandas.DataFrame(dict(passes=labels, percent_ran=percentages))

  logging.info('Finished loading data, generating figures.')

  figure = plotly.express.bar(
      final_data,
      log_y=FLAGS.log_scale,
      x='passes',
      y='percent_ran',
      width=2000,
      height=800)
  figure.write_image(FLAGS.output_file)


if __name__ == '__main__':
  app.run(main)

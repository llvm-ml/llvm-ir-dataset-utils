"""A tool for generating visualizations of bitcode distributions across
languages.
"""

import logging
import os
import csv

import pandas
import plotly.express

from absl import app
from absl import flags

FLAGS = flags.FLAGS

flags.DEFINE_multi_string('bc_dist_file', None, 'The path to a data file.')
flags.DEFINE_string('output_file', None, 'The path to the output image.')

flags.mark_flag_as_required('bc_dist_file')
flags.mark_flag_as_required('output_file')


def compute_cumulative_histogram_from_file(file_path):
  histogram = {}
  with open(file_path) as bc_dist_file:
    dict_reader = csv.DictReader(bc_dist_file)
    for data_row in dict_reader:
      for instruction_type in data_row:
        if instruction_type == 'name':
          continue
        instruction_count = int(data_row[instruction_type])
        if instruction_type in histogram:
          histogram[instruction_type] += instruction_count
        else:
          histogram[instruction_type] = instruction_count
  return histogram


def main(_):
  distributions = {}
  instruction_names = []
  for bc_dist_file_path in FLAGS.bc_dist_file:
    language_name = os.path.basename(bc_dist_file_path)[:-4]
    distribution = compute_cumulative_histogram_from_file(bc_dist_file_path)
    instruction_names = list(set(instruction_names + list(distribution.keys())))
    distributions[language_name] = distribution

  # Ensure that all languages have the same opcodes.
  for distribution in distributions:
    for instruction_name in instruction_names:
      if instruction_name not in distributions[distribution]:
        distributions[distribution][instruction_name] = 0

  # Normalize the distributions in each language by the instruction count
  for distribution in distributions:
    total_instruction_count = 0
    for instruction_name in distributions[distribution]:
      total_instruction_count += distributions[distribution][instruction_name]
    for instruction_name in distributions[distribution]:
      distributions[distribution][instruction_name] = distributions[
          distribution][instruction_name] / total_instruction_count

  language_names = []
  instructions = []
  instruction_counts = []

  for language_name in distributions:
    for instruction in distributions[language_name]:
      language_names.append(language_name)
      instructions.append(instruction)
      instruction_counts.append(distributions[language_name][instruction])

  data_frame = pandas.DataFrame({
      'language': language_names,
      'instruction': instructions,
      'count': instruction_counts
  })

  figure = plotly.express.bar(
      data_frame, x='language', y='count', color='instruction')

  figure.write_image(FLAGS.output_file)


if __name__ == '__main__':
  app.run(main)

"""Visualization tool for generating a treemap of size information."""

import logging
import os

import plotly.express

from absl import flags
from absl import app

import ray

FLAGS = flags.FLAGS

flags.DEFINE_multi_string(
    'size_file', None,
    'A size file to load data from. Can be specified more than once.')
flags.DEFINE_string('output_file', None,
                    'The output file to place the image in.')
flags.DEFINE_integer('max_projects', 1000,
                     'The max number of projects to include from a language.')

flags.mark_flag_as_required('size_file')
flags.mark_flag_as_required('output_file')


def load_sizes_file(size_file_path):
  with open(size_file_path) as size_file:
    name_size_pairs = []
    for line in size_file:
      name_size_pair = line.rstrip().split(',')
      name_size_pairs.append((name_size_pair[0], int(name_size_pair[1])))
  # Get the basename of the file without the extension
  language_name = os.path.basename(size_file_path)[:-4]
  names = [language_name]
  languages = ['']
  values = [0]
  for name, size in name_size_pairs[:FLAGS.max_projects]:
    names.append(name)
    languages.append(language_name)
    values.append(size)
  return (names, languages, values)


def main(_):
  names = []
  languages = []
  sizes = []

  for size_file in FLAGS.size_file:
    new_names, new_languages, new_sizes = load_sizes_file(size_file)
    names.extend(new_names)
    languages.extend(new_languages)
    sizes.extend(new_sizes)

  figure = plotly.express.treemap(
      names=names,
      parents=languages,
      values=sizes,
      color=sizes,
      color_continuous_scale='RdBu')

  figure.write_image(FLAGS.output_file)


if __name__ == '__main__':
  app.run(main)

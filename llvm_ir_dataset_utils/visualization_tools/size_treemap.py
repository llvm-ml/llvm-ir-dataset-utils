"""Visualization tool for generating a treemap of size information."""

import logging
import os

import pandas

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
flags.DEFINE_integer(
    'size_threshold', 100 * 1000**2,
    'The size threshold before putting a project in the other category (in bytes).'
)

flags.mark_flag_as_required('size_file')
flags.mark_flag_as_required('output_file')


def load_sizes_file(size_file_path):
  other_size = 0
  with open(size_file_path) as size_file:
    name_size_pairs = []
    for line in size_file:
      name_size_pair = line.rstrip().split(',')
      name = name_size_pair[0]
      size = int(name_size_pair[1])
      if size < FLAGS.size_threshold:
        other_size += size
        continue
      name_size_pairs.append((name, size))
  # Get the basename of the file without the extension
  language_name = os.path.basename(size_file_path)[:-4]
  names = [language_name]
  languages = ['']
  values = [0]
  for name, size in name_size_pairs:
    names.append(name)
    languages.append(language_name)
    values.append(size)
  names.append(f'Small {language_name} projects.')
  languages.append(language_name)
  values.append(other_size)
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

  data_frame = pandas.DataFrame(
      list(zip(names, languages, sizes)),
      columns=['names', 'languages', 'sizes'])

  figure = plotly.express.treemap(
      data_frame=data_frame,
      names='names',
      parents='languages',
      values='sizes',
      color='sizes',
      color_continuous_scale='Aggrnyl',
      width=1100,
      height=550)

  figure.update_layout(margin=dict(l=20, r=20, t=20, b=20),)

  figure.write_image(FLAGS.output_file)


if __name__ == '__main__':
  app.run(main)

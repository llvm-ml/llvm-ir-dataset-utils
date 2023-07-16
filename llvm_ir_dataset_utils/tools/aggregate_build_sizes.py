"""Tool for aggregating and providing statistics on bitcode size."""

import os
import json

from absl import flags
from absl import app
from absl import logging

import ray

FLAGS = flags.FLAGS

flags.DEFINE_string('corpus_dir', None, 'The base directory of the corpus')
flags.DEFINE_string(
    'per_package_output', None,
    'The path to a CSV file containing the name of each package and the amount '
    'of bitcode that it has.')

flags.mark_flag_as_required('corpus_dir')


@ray.remote
def get_size_from_manifest(build_manifest_path):
  if not os.path.exists(build_manifest_path):
    logging.warning(
        f'Expected build manifest at path {build_manifest_path} does not exist.'
    )
    return (build_manifest_path, 0)
  with open(build_manifest_path) as build_manifest_file:
    build_manifest = json.load(build_manifest_file)
    package_name_hash = os.path.basename(os.path.dirname(build_manifest_path))
    return (package_name_hash, build_manifest['size'])


def main(_):
  subfolders = os.listdir(FLAGS.corpus_dir)
  logging.info(f'Gathering data from {len(subfolders)} builds.')
  size_futures = []
  for subfolder in subfolders:
    build_manifest_path = os.path.join(FLAGS.corpus_dir, subfolder,
                                       'build_manifest.json')
    size_futures.append(get_size_from_manifest.remote(build_manifest_path))
  names_sizes = ray.get(size_futures)

  size_sum = 0
  for name_size in names_sizes:
    size_sum += name_size[1]
  logging.info(f'Aggregate size:{size_sum}')

  if FLAGS.per_package_output is not None:
    names_sizes = sorted(names_sizes, key=lambda name_size: name_size[1])
    with open(FLAGS.per_package_output, 'w') as per_package_index_file:
      for name_size in names_sizes:
        per_package_index_file.write(f'{name_size[0]},{name_size[1]}\n')


if __name__ == '__main__':
  app.run(main)

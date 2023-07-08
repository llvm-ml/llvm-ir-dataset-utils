"""Tool for aggregating and providing statistics on bitcode size."""

import os
import json

from absl import flags
from absl import app
from absl import logging

import ray

FLAGS = flags.FLAGS

flags.DEFINE_string('corpus_dir', None, 'The base directory of the corpus')

flags.mark_flag_as_required('corpus_dir')


@ray.remote
def get_size_from_manifest(build_manifest_path):
  if not os.path.exists(build_manifest_path):
    logging.warn(
        f'Expected build manifest at path {build_manifest_path} does not exist.'
    )
    return 0
  with open(build_manifest_path) as build_manifest_file:
    build_manifest = json.load(build_manifest_file)
    return build_manifest['size']


def main(_):
  subfolders = os.listdir(FLAGS.corpus_dir)
  logging.info(f'Gathering data from {len(subfolders)} builds.')
  size_futures = []
  for subfolder in subfolders:
    build_manifest_path = os.path.join(FLAGS.corpus_dir, subfolder,
                                       'build_manifest.json')
    size_futures.append(get_size_from_manifest.remote(build_manifest_path))
  sizes = ray.get(size_futures)
  logging.info(sum(sizes))


if __name__ == '__main__':
  app.run(main)

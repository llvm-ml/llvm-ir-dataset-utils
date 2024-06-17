"""Tool for building a list of self contained sources."""

import logging
import json

from absl import app
from absl import flags

import ray

from llvm_ir_dataset_utils.builders import builder

FLAGS = flags.FLAGS

flags.DEFINE_string('batch_list', None, 'The path to the batch list.')
flags.DEFINE_string('source_dir', '/tmp/source',
                    'The path to the source dir. Not used by this builder.')
flags.DEFINE_string('build_dir', None, 'The path to the build dir.')
flags.DEFINE_string('corpus_dir', None, 'The directory to place the corpus in.')
flags.DEFINE_bool(
    'archive_corpus', False,
    'Whether or not to put the output corpus into an arxiv to reduce inode usage'
)


def main(_):
  ray.init()

  with open(FLAGS.batch_list) as batch_list_handle:
    batch_list = json.load(batch_list_handle)

  batch_futures = []

  for index, batch_info in enumerate(batch_list['batches']):
    corpus_description = {
        'sources': [],
        'folder_name': f'batch-{index}',
        'build_system': 'self_contained',
        'package_name': 'batch-{index}',
        'license': 'UNKNOWN',
        'license_source': None,
        'source_file_list': batch_info
    }

    batch_futures.append(
        builder.get_build_future(
            corpus_description,
            FLAGS.source_dir,
            FLAGS.build_dir,
            FLAGS.corpus_dir,
            1, {},
            cleanup=True,
            archive_corpus=FLAGS.archive_corpus))

  while len(batch_futures) > 0:
    finished, batch_futures = ray.wait(batch_futures, timeout=5.0)
    finished_data = ray.get(finished)
    logging.info(
        f'Just finished {len(finished_data)}, {len(batch_futures)} remaining.')


if __name__ == '__main__':
  app.run(main)

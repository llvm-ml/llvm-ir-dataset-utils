"""Tool for building a list of julia packages."""

from absl import app
from absl import flags
import logging

import ray

from llvm_ir_dataset_utils.builders import builder

FLAGS = flags.FLAGS

flags.DEFINE_string('package_list', None, 'The path to the package list.')
flags.DEFINE_string('source_dir', '/tmp/source',
                    'Path to a directory to download source code into.')
flags.DEFINE_string('build_dir', None,
                    'The base directory to perform builds in.')
flags.DEFINE_string('corpus_dir', None, 'The directory to place the corpus in.')
flags.DEFINE_integer('thread_count', 1,
                     'The number of threads to use per package build.')

flags.mark_flag_as_required('build_dir')
flags.mark_flag_as_required('corpus_dir')
flags.mark_flag_as_required('package_list')


def main(_):
  ray.init()

  with open(FLAGS.package_list) as package_list_file:
    package_list = [package_name.rstrip() for package_name in package_list_file]

  build_futures = []
  for package_name in package_list:
    corpus_description = {
        'sources': [],
        'folder_name': package_name,
        'build_system': 'julia',
        'package_name': package_name
    }

    build_futures.append(
        builder.get_build_future(
            corpus_description,
            FLAGS.source_dir,
            FLAGS.build_dir,
            FLAGS.corpus_dir,
            FLAGS.thread_count, {},
            cleanup=True))

  while len(build_futures) > 0:
    finished, build_futures = ray.wait(build_futures, timeout=5.0)
    finished_data = ray.get(finished)
    logging.info(
        f'Just finished {len(finished_data)}, {len(build_futures)} remaining.')


if __name__ == '__main__':
  app.run(main)

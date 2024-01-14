"""A script for uploading a dataset in the form of a folder of parquet files
to huggingface.
"""

import logging
import os

from absl import app
from absl import flags

from huggingface_hub import HfApi

FLAGS = flags.FLAGS

flags.DEFINE_string('dataset_dir', None,
                    'The path to the folder containing the parquet files.')
flags.DEFINE_string('start_after', None, 'A specific path to start at.')

flags.mark_flag_as_required('dataset_dir')


def main(_):
  logging.info('Starting the upload')
  api = HfApi()
  for file_to_upload in os.listdir(FLAGS.dataset_dir):
    if FLAGS.start_after and file_to_upload <= FLAGS.start_after:
      logging.info(f'Skipping uploading {file_to_upload}')
      continue

    full_file_path = os.path.join(FLAGS.dataset_dir, file_to_upload)
    api.upload_file(
        path_or_fileobj=full_file_path,
        path_in_repo=file_to_upload,
        repo_id='llvm-ml/ComPile',
        repo_type='dataset')
    logging.info(f'Finished uploading {file_to_upload}')


if __name__ == '__main__':
  app.run(main)

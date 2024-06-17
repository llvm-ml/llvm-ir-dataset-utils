"""Tool for gathering self-contained source files so they can be built later."""

import os
import shutil
import logging
import json
import glob

from absl import app
from absl import flags

from llvm_ir_dataset_utils.util import parallel

FLAGS = flags.FLAGS

flags.DEFINE_string('folder', None, 'The folder to look for source files in.')
flags.DEFINE_string('output_file', None,
                    'The path to a JSON file to dump the output into.')

flags.mark_flag_as_required('folder')
flags.mark_flag_as_required('output_file')

SOURCE_EXTENSION = 'c'
SOURCE_FILES_PER_BATCH = 64


def find_files(folder_path):
  file_names = []

  folder_glob = os.path.join(folder_path, f'**/*.{SOURCE_EXTENSION}')
  for file_name in glob.glob(
      os.path.join(folder_path, f'**/*.{SOURCE_EXTENSION}'), recursive=True):
    file_names.append(file_name)

  return file_names


def main(_):
  source_files = find_files(FLAGS.folder)

  logging.info(f'Done collecting source files, found {len(source_files)}')

  batches = parallel.split_batches(source_files, SOURCE_FILES_PER_BATCH)

  logging.info(f'Done creating batches, have {len(batches)}')

  output_spec = {'batches': batches}

  with open(FLAGS.output_file, 'w') as output_file_handle:
    json.dump(output_spec, output_file_handle, indent=4)

  logging.info('Finished outputting batches')


if __name__ == '__main__':
  app.run(main)

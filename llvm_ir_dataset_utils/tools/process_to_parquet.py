"""This is a script that allows for the conversion of a deduplicated dataset
into a parquet dataset for distribution.
"""

import logging
import os
import sys
import glob

from absl import app
from absl import flags

import pandas

import pyarrow

from pyarrow import parquet

from llvm_ir_dataset_utils.util import dataset_corpus

FLAGS = flags.FLAGS

flags.DEFINE_string('corpus_dir', None, 'The corpus to pull bitcode from.')
flags.DEFINE_integer('max_batches', sys.maxsize,
                     'The maximum number of projects to process')

flags.mark_flag_as_required('corpus_dir')


def process_single_batch(batch_dir, dataset_dir):
  try:
    bitcode_paths = dataset_corpus.get_bitcode_file_paths(batch_dir)
    license_information = dataset_corpus.load_json_from_corpus(
        batch_dir, './license_info.json')
  except:
    logging.warning('Failed to get bitcode_paths')
    return
  module_content = []
  license_expression = []
  license_source = []
  license_file = []
  package_source = []

  for bitcode_path in bitcode_paths:
    bitcode_file_data = dataset_corpus.load_file_from_corpus(
        batch_dir, bitcode_path)
    module_content.append(bitcode_file_data)

    # Cut off the first two characters and the last two characters as we only
    # want the raw module hash.
    bitcode_license_info = license_information[bitcode_path[2:-3]]
    license_expression.append(bitcode_license_info[0])
    license_source.append(bitcode_license_info[1])
    license_file.append(bitcode_license_info[2])
    package_source.append(bitcode_license_info[3])

  dataframe = pandas.DataFrame.from_dict({
      'content': module_content,
      'license_expression': license_expression,
      'license_source': license_source,
      'license_files': license_file,
      'package_source': package_source
  })

  table = pyarrow.Table.from_pandas(dataframe, preserve_index=False)

  parquet.write_table(table, dataset_dir)


def main(_):
  projects_list = os.listdir(FLAGS.corpus_dir)

  logging.info(f'Processing {len(projects_list)} projects')

  for index, project_dir in enumerate(projects_list):
    batch_path = os.path.join(FLAGS.corpus_dir, project_dir)
    process_single_batch(batch_path, '/tmp/test.parquet')
    logging.info(f'Just finished processing {project_dir}')

    if index >= FLAGS.max_batches:
      break


if __name__ == '__main__':
  app.run(main)

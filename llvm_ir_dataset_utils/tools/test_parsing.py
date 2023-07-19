"""Tool for testing parsing of all bitcode files in a corpus using opt."""

import pathlib
import os
import subprocess

from absl import logging
from absl import app
from absl import flags

import ray

FLAGS = flags.FLAGS

flags.DEFINE_string('corpus_dir', None, 'The path to the corpus directory.')


def process_bitcode_file(bitcode_file_path):
  # TODO(boomanaiden154): Update the version of opt to use the generic version
  # once the symlink has been added to the container image.
  command_vector = ['opt-16', bitcode_file_path, '-o', '/dev/null']
  command_output = subprocess.run(
      command_vector, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  return command_output.returncode == 0


@ray.remote(num_cpus=1)
def process_folder(folder_path):
  bitcode_files = pathlib.Path(folder_path).glob('**/*.bc')
  opt_success = 0
  opt_failure = 0
  for bitcode_file in bitcode_files:
    file_status = process_bitcode_file(bitcode_file)
    if file_status:
      opt_success += 1
    else:
      opt_failure += 1
  return (opt_success, opt_failure)


def main(_):
  corpus_folders = os.listdir(FLAGS.corpus_dir)

  folder_processing_futures = []
  for corpus_folder in corpus_folders:
    corpus_folder_full_path = os.path.join(FLAGS.corpus_dir, corpus_folder)
    folder_processing_future = process_folder.remote(corpus_folder_full_path)
    folder_processing_futures.append(folder_processing_future)

  opt_success = 0
  opt_failure = 0
  while len(folder_processing_futures) > 0:
    finished, folder_processing_futures = ray.wait(
        folder_processing_futures, timeout=5.0)
    finished_data = ray.get(finished)
    for finished_section in finished_data:
      opt_success += finished_section[0]
      opt_failure += finished_section[1]
    logging.info(
        f'Just finished {len(finished_data)}, {len(folder_processing_futures)} remaining.'
    )
  logging.info(f'Got {opt_success} successes and {opt_failure} failures.')


if __name__ == '__main__':
  app.run(main)

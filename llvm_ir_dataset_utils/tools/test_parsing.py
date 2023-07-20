"""Tool for testing parsing of all bitcode files in a corpus using opt."""

import pathlib
import os
import subprocess

from absl import logging
from absl import app
from absl import flags

import ray

BITCODE_FILE_CHUNK_SIZE = 16

FLAGS = flags.FLAGS

flags.DEFINE_string('corpus_dir', None, 'The path to the corpus directory.')
flags.DEFINE_boolean(
    'log_failures', False,
    'Whether or not to output the paths to all the bitcode files that failed '
    'to parse.')


@ray.remote(num_cpus=1)
def process_bitcode_files(bitcode_file_paths):
  # TODO(boomanaiden154): Update the version of opt to use the generic version
  # once the symlink has been added to the container image.
  file_statuses = []
  for bitcode_file_path in bitcode_file_paths:
    command_vector = ['opt-16', bitcode_file_path, '-o', '/dev/null']
    command_output = subprocess.run(
        command_vector, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if command_output.returncode == 0:
      file_statuses.append(None)
    else:
      file_statuses.append(bitcode_file_path)
  return file_statuses


@ray.remote(num_cpus=1)
def process_folder(folder_path):
  # TODO(boomanaiden154): Switch to pulling bitcode files from the meta corpus
  # description once that is available and ready rather than the strategy being
  # used here.
  bitcode_files_gen = pathlib.Path(folder_path).glob('**/*.bc')
  bitcode_files = list(bitcode_files_gen)

  file_status_futures = []
  current_start_index = 0
  while True:
    end_index = current_start_index + BITCODE_FILE_CHUNK_SIZE
    bitcode_file_chunk = bitcode_files[current_start_index:end_index]
    file_status_future = process_bitcode_files.remote(bitcode_file_chunk)
    file_status_futures.append(file_status_future)
    current_start_index = end_index
    if current_start_index + BITCODE_FILE_CHUNK_SIZE >= len(bitcode_files):
      bitcode_file_last_chunk = bitcode_files[current_start_index:]
      file_status_last_future = process_bitcode_files.remote(
          bitcode_file_last_chunk)
      file_status_futures.append(file_status_last_future)
      break

  file_statuses = ray.get(file_status_futures)

  opt_success = 0
  opt_failures = []
  for file_status_chunk in file_statuses:
    for file_status in file_status_chunk:
      if file_status:
        opt_failures.append(file_status)
      else:
        opt_success += 1
  return (opt_success, opt_failures)


def main(_):
  corpus_folders = os.listdir(FLAGS.corpus_dir)

  folder_processing_futures = []
  for corpus_folder in corpus_folders:
    corpus_folder_full_path = os.path.join(FLAGS.corpus_dir, corpus_folder)
    folder_processing_future = process_folder.remote(corpus_folder_full_path)
    folder_processing_futures.append(folder_processing_future)

  opt_success = 0
  opt_failures = []
  while len(folder_processing_futures) > 0:
    to_wait_for = 128
    if len(folder_processing_futures) < 256:
      to_wait_for = 1
    finished, folder_processing_futures = ray.wait(
        folder_processing_futures, timeout=5.0, num_returns=to_wait_for)
    finished_data = ray.get(finished)
    for finished_section in finished_data:
      opt_success += finished_section[0]
      opt_failures.extend(finished_section[1])
    logging.info(
        f'Just finished {len(finished_data)}, {len(folder_processing_futures)} remaining.'
    )
  logging.info(f'Got {opt_success} successes and {len(opt_failures)} failures.')

  if FLAGS.log_failures:
    for failure in opt_failures:
      logging.info(f'{failure} failed.')


if __name__ == '__main__':
  app.run(main)

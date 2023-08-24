"""Tools for working with llvm-ir-dataset-utls corpora"""

import tarfile
import logging
import os
import json


def load_file_from_corpus(corpus_path, file_name):
  if corpus_path[-3:] == "tar":
    with tarfile.open(corpus_path) as build_archive:
      try:
        file_to_extract = build_archive.extractfile(file_name)
        return file_to_extract.read()
      except (tarfile.TarError, KeyError):
        logging.warning(
            f'Failed to read {file_name} in {corpus_path}: tar archive error.')
        return None
  else:
    file_path = os.path.join(corpus_path, file_name)
    if not os.path.exists(file_path):
      logging.warning(f'Expected {file_name} in {corpus_path} does not exist.')
      return None
    with open(file_path, 'rb') as file_to_read:
      return file_to_read.read()


def load_json_from_corpus(corpus_path, file_name):
  file_contents = load_file_from_corpus(corpus_path, file_name)
  if file_contents is None:
    # Error logging should be handled by load_file_from_corpus
    return None
  return json.loads(file_contents)


def get_bitcode_file_paths(corpus_path):
  # TODO(boomanaiden154): This (and probably other parts) don't support meta
  # corpora like what we get from the rust builder. This needs to be addressed.
  corpus_description = load_json_from_corpus(corpus_path,
                                             './corpus_description.json')
  return ['./' + module + '.bc' for module in corpus_description['modules']]


def get_corpus_name(corpus_path):
  if corpus_path[-3:] == 'tar':
    return os.path.basename(corpus_path)[:-4]
  return os.path.basename(corpus_path)

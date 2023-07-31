"""Tools for working with llvm-ir-dataset-utls corpora"""

import tarfile
import logging
import os
import json

def load_file_from_corpus(corpus_path, file_name):
  if corpus_path[-3:] == "tar":
    build_archive = tarfile.open(corpus_path)
    with tarfile.open(corpus_path) as build_archive:
      try:
        file_to_extract = build_archive.extractfile(file_name)
        return file_to_extract.read()
      except tarfile.TarError:
        logging.warning(f'Failed to read {file_name} in {corpus_path}: tar archive error.')
        return None
  else:
    file_path = os.path.join(corpus_path, file_name)
    if not os.path.exists(file_path):
      logging.warning(f'Expected {file_name} in {corpus_path} does not exist.')
      return None
    with open(file_path) as file_to_read:
      return file_to_read.read()

def load_json_from_corpus(corpus_path, file_name):
  file_contents = load_file_from_corpus(corpus_path, file_name)
  if file_contents is None:
    # Error logging should be handled by load_file_from_corpus
    return None
  return json.loads(file_contents)


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


def get_bitcode_file_paths(corpus_path, filter='none'):
  corpus_description = load_json_from_corpus(corpus_path,
                                             './corpus_description.json')
  if filter == 'none':
    return ['./' + module + '.bc' for module in corpus_description['modules']]
  else:
    # We're assuming here that if a corpus description has a global
    # command override section that we don't have individual compilation
    # command sections.
    if "global_command_override" in corpus_description:
      return ValueError("Bitcode modules don't have .llvmcmd section.")

  modules_matching_filter = []

  for module in corpus_description['modules']:
    command_line_path = './' + module + '.cmd'
    command_line = load_file_from_corpus(corpus_path,
                                         command_line_path).decode('utf-8')
    # This is a very hacky heuristic, mostly based on how many include paths
    # the driver tries to add to the frontend command line. Might need to be
    # fixed in the future for portability.
    if filter == 'cpp' and command_line.count('c++') >= 4:
      modules_matching_filter.append('./' + module + '.bc')
    elif filter == 'c' and command_line.count('c++') <= 1:
      modules_matching_filter.append('./' + module + '.bc')
    else:
      raise ValueError('Invalid filter')

  return modules_matching_filter


def get_corpus_name(corpus_path):
  if corpus_path[-3:] == 'tar':
    return os.path.basename(corpus_path)[:-4]
  return os.path.basename(corpus_path)

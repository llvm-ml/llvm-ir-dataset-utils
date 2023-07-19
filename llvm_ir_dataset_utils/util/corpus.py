"""Utilities for working with ml-compiler-opt corpora"""

import pathlib
import json


def get_corpus_description_paths(meta_corpus_dir):
  return pathlib.Path(meta_corpus_dir).glob('**/corpus_description.json')


def create_meta_corpus(meta_corpus_dir):
  corpus_description_file_paths = get_corpus_description_paths(meta_corpus_dir)
  corpus_descriptions = []
  for corpus_description_file_path in corpus_description_file_paths:
    with open(corpus_description_file_path) as corpus_description_file:
      corpus_descriptions.append(json.load(corpus_description_file))

  meta_corpus_description = {
      'corpora': corpus_descriptions,
      'corpus_references': []
  }

  return meta_corpus_description

"""A script for collecting a large amount of textual IR into a single file,
aimed primarily at training basic BPE tokenizers."""

import os
import logging
import subprocess

from absl import app
from absl import flags

from llvm_ir_dataset_utils.util import dataset_corpus
from llvm_ir_dataset_utils.util import bitcode_module

FLAGS = flags.FLAGS

flags.DEFINE_multi_string(
    'corpus_dir', None,
    'The corpora to use for generating the set of textual IR.')
flags.DEFINE_string('output_file', None,
                    'The output file to put all the textual IR into.')
flags.DEFINE_integer('max_projects', 10,
                     'The maximum number of projects per corpus.')

flags.mark_flag_as_required('corpus_dir')
flags.mark_flag_as_required('output_file')


# TODO(boomanaiden154): Could probably be unified with part of the get_size_text
# implementation in bitcode_module.py
def get_textual_ir(bitcode_module):
  dis_command_vector = ['llvm-dis', '-']
  with subprocess.Popen(
      dis_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      stdin=subprocess.PIPE) as dis_process:
    return dis_process.communicate(input=bitcode_module)[0].decode('utf-8')


def process_single_project(project_dir):
  all_textual_ir = ''
  try:
    bitcode_paths = dataset_corpus.get_bitcode_file_paths(project_dir, 'none')
  except:
    return ''
  for bitcode_path in bitcode_paths:
    bitcode_module = dataset_corpus.load_file_from_corpus(
        project_dir, bitcode_path)
    textual_ir = get_textual_ir(bitcode_module)
    all_textual_ir += textual_ir
  return all_textual_ir


def main(_):
  all_textual_ir = ''

  for corpus_dir in FLAGS.corpus_dir:
    for project_dir in os.listdir(corpus_dir)[:FLAGS.max_projects]:
      logging.info(f'Processing {project_dir} in {corpus_dir}')
      full_project_dir = os.path.join(corpus_dir, project_dir)
      all_textual_ir += process_single_project(full_project_dir)

  with open(FLAGS.output_file, 'w') as output_file:
    output_file.write(all_textual_ir)


if __name__ == '__main__':
  app.run(main)

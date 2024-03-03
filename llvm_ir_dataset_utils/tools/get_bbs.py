"""Tool for extracting basic blocks from the corpus"""

import os
import logging
import subprocess
import json
import binascii
import tempfile

from absl import app
from absl import flags

import ray

from llvm_ir_dataset_utils.util import bitcode_module
from llvm_ir_dataset_utils.util import dataset_corpus
from llvm_ir_dataset_utils.util import parallel

FLAGS = flags.FLAGS

flags.DEFINE_multi_string('corpus_dir', None,
                          'The corpus directory to look for project in.')
flags.DEFINE_string('output_file', None,
                    'The output file to put unique BBs in.')

flags.mark_flag_as_required('corpus_dir')
flags.mark_flag_as_required('output_file')

OPT_PASS_LIST = ['default<O0>', 'default<O1>', 'default<O2>', 'default<O3>']
LLC_OPT_LEVELS = ['-O0', '-O1', '-O2', '-O3']

PROJECT_MODULE_CHUNK_SIZE = 8


def get_bb_addr_map(input_file_path):
  bb_addr_map_command_vector = [
      'llvm-readobj', '--bb-addr-map', '--elf-output-style=JSON',
      input_file_path
  ]
  with subprocess.Popen(
      bb_addr_map_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE) as readobj_process:
    out, err = readobj_process.communicate()
    basic_block_address_maps = json.loads(out.decode('utf-8'))[0]
    if 'BBAddrMap' not in basic_block_address_maps:
      # TODO(boomanaiden154): More investigation here. Currently only seems to
      # happen in the case of empty modules.
      logging.warning(f'Failed to get BBAddrMap info {input_file_path}')
      return []
    return basic_block_address_maps['BBAddrMap']


def get_text_section_offset(input_file_path):
  readobj_command_vector = [
      'llvm-readobj', '--sections', '--elf-output-style=JSON', input_file_path
  ]
  with subprocess.Popen(
      readobj_command_vector, stdout=subprocess.PIPE,
      stderr=subprocess.PIPE) as readobj_process:
    out, err = readobj_process.communicate()
    sections_list = json.loads(out.decode('utf-8'))[0]['Sections']
    #assert (len(sections_list) == 10)
    for section in sections_list:
      section_name = section['Section']['Name']['Name']
      if section_name == '.text':
        section_offset = section['Section']['Offset']
        return section_offset


def get_basic_blocks(input_file_path):
  basic_block_map = get_bb_addr_map(input_file_path)

  basic_blocks = []

  text_section_offset = get_text_section_offset(input_file_path)

  with open(input_file_path, 'rb') as input_file_handle:
    binary_data = input_file_handle.read()
    for function in basic_block_map:
      function_start = function['Function']['At']
      for bb_entry in function['Function']['BB entries']:
        # TODO(boomanaiden154): This needs to be updated once we bump the toolchain
        # and end up using BBAddrMap v2 (or after some cutoff).
        bb_offset = bb_entry["Offset"]
        bb_size = bb_entry["Size"]
        current_index = function_start + text_section_offset + bb_offset
        bb_hex = binascii.hexlify(binary_data[current_index:current_index +
                                              bb_size]).decode("utf-8")
        basic_blocks.append(bb_hex)

  return basic_blocks


def output_optimized_bc(input_file_path, pass_list, output_file_path):
  opt_command_vector = [
      'opt', f'-passes={pass_list}', input_file_path, '-o', output_file_path
  ]
  opt_output = subprocess.run(
      opt_command_vector, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  assert (opt_output.returncode == 0)


def get_asm_lowering(input_file_path, opt_level, output_file_path):
  llc_command_vector = [
      'llc', opt_level, input_file_path, '-filetype=obj',
      '-basic-block-sections=labels', '-o', output_file_path
  ]
  llc_output = subprocess.run(
      llc_command_vector, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  assert (llc_output.returncode == 0)


def process_bitcode_file(bitcode_file_path):
  # Get basic blocks from the unoptimized version, and at all optimization levels.
  basic_blocks = []
  with tempfile.TemporaryDirectory() as temp_dir:
    for index, opt_pass in enumerate(OPT_PASS_LIST):
      bc_output_path = os.path.join(temp_dir, f'{index}.bc')
      output_optimized_bc(bitcode_file_path, opt_pass, bc_output_path)
      for index, llc_level in enumerate(LLC_OPT_LEVELS):
        asm_output_path = f'{bc_output_path}.{index}.o'
        get_asm_lowering(bc_output_path, llc_level, asm_output_path)
        basic_blocks.extend(get_basic_blocks(asm_output_path))

  return list(set(basic_blocks))


def process_modules_batch(project_path, modules_batch):
  basic_blocks = []

  for bitcode_module in modules_batch:
    module_data = dataset_corpus.load_file_from_corpus(project_path,
                                                       bitcode_module)
    if module_data is None:
      continue

    with tempfile.NamedTemporaryFile() as temp_bc_file:
      temp_bc_file.write(module_data)
      basic_blocks.extend(process_bitcode_file(temp_bc_file.file.name))

  return list(set(basic_blocks))


def process_project(project_path):
  basic_blocks = []
  bitcode_modules = dataset_corpus.get_bitcode_file_paths(project_path)

  module_batches = parallel.split_batches(bitcode_modules,
                                          PROJECT_MODULE_CHUNK_SIZE)

  for module_batch in module_batches:
    basic_blocks.extend(process_modules_batch(project_path, module_batch))

  return list(set(basic_blocks))


def main(_):
  project_dirs = []

  for corpus_dir in FLAGS.corpus_dir:
    for project_dir in os.listdir(corpus_dir):
      project_dirs.append(os.path.join(corpus_dir, project_dir))

  basic_blocks = []
  for project_dir in project_dirs:
    basic_blocks.extend(process_project(project_dir))

  basic_blocks = list(set(basic_blocks))

  with open(FLAGS.output_file, 'w') as output_file_handle:
    for basic_block in basic_blocks:
      output_file_handle.write(f'{basic_block}\n')


if __name__ == '__main__':
  app.run(main)

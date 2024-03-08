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
  if llc_output.returncode != 0:
    logging.warning(f'Failed to lower {input_file_path} to asm')
  return llc_output.returncode == 0


def process_bitcode_file(bitcode_file_path):
  # Get basic blocks from the unoptimized version, and at all optimization levels.
  basic_blocks = []
  with tempfile.TemporaryDirectory() as temp_dir:
    for index, opt_pass in enumerate(OPT_PASS_LIST):
      bc_output_path = os.path.join(temp_dir, f'{index}.bc')
      output_optimized_bc(bitcode_file_path, opt_pass, bc_output_path)
      for index, llc_level in enumerate(LLC_OPT_LEVELS):
        asm_output_path = f'{bc_output_path}.{index}.o'
        asm_lowering_output = get_asm_lowering(bc_output_path, llc_level,
                                               asm_output_path)
        # Only get the basic blocks from the lowered file if we successfully
        # lower the bitcode.
        if asm_lowering_output:
          basic_blocks.extend(get_basic_blocks(asm_output_path))

  return list(set(basic_blocks))


@ray.remote(num_cpus=1)
def process_modules_batch(modules_batch):
  basic_blocks = []

  for bitcode_module_info in modules_batch:
    project_path, bitcode_module = bitcode_module_info
    module_data = dataset_corpus.load_file_from_corpus(project_path,
                                                       bitcode_module)
    if module_data is None:
      continue

    with tempfile.NamedTemporaryFile() as temp_bc_file:
      temp_bc_file.write(module_data)
      basic_blocks.extend(process_bitcode_file(temp_bc_file.file.name))

  return list(set(basic_blocks))


# TODO(boomanaiden154): Abstract the infrastructure to parse modules into
# batches into somewhere common as it is used in several places already,
# including grep_source.py.
@ray.remote(num_cpus=1)
def get_bc_files_in_project(project_path):
  try:
    bitcode_modules = dataset_corpus.get_bitcode_file_paths(project_path)
  except:
    return []

  return [(project_path, bitcode_module) for bitcode_module in bitcode_modules]


def get_bbs_from_projects(project_list, output_file_path):
  logging.info(f'Processing {len(project_list)} projects.')

  project_info_futures = []

  for project_path in project_list:
    project_info_futures.append(get_bc_files_in_project.remote(project_path))

  project_infos = []

  while len(project_info_futures) > 0:
    to_return = 32 if len(project_info_futures) > 64 else 1
    finished, project_info_futures = ray.wait(
        project_info_futures, timeout=5.0, num_returns=to_return)
    logging.info(
        f'Just finished gathering modules from {len(finished)} projects, {len(project_info_futures)} remaining.'
    )
    for finished_project in ray.get(finished):
      project_infos.extend(finished_project)

  logging.info(
      f'Finished gathering modules, currently have {len(project_infos)}')

  module_batches = parallel.split_batches(project_infos,
                                          PROJECT_MODULE_CHUNK_SIZE)

  logging.info(f'Setup {len(module_batches)} batches.')

  module_batch_futures = []

  for module_batch in module_batches:
    module_batch_futures.append(process_modules_batch.remote(module_batch))

  with open(output_file_path, 'w') as output_file_handle:
    while len(module_batch_futures) > 0:
      to_return = 32 if len(module_batch_futures) > 64 else 1
      finished, module_batch_futures = ray.wait(
          module_batch_futures, timeout=5.0, num_returns=to_return)
      logging.info(
          f'Just finished {len(finished)} batches, {len(module_batch_futures)} remaining.'
      )
      for finished_batch in ray.get(finished):
        for basic_block in finished_batch:
          output_file_handle.write(f'{basic_block}\n')


def main(_):
  project_dirs = []

  for corpus_dir in FLAGS.corpus_dir:
    for project_dir in os.listdir(corpus_dir):
      project_dirs.append(os.path.join(corpus_dir, project_dir))

  basic_blocks = get_bbs_from_projects(project_dirs, FLAGS.output_file)


if __name__ == '__main__':
  app.run(main)

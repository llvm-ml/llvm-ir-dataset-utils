"""Tool for getting statistics on bitcode modules."""

import os
import glob
import logging

from absl import app
from absl import flags

from llvm_ir_dataset_utils.util import bitcode_module

FLAGS = flags.FLAGS

# TODO(boomanaiden154): Refactor this to a corpus directory, maybe with a sampling/filtering
# clause to allow for smaller scale testing.
flags.DEFINE_string('project_dir', None,
                    'The corpus directory to look for modules in.')
flags.DEFINE_string('output_file_path', None, 'The output file.')

flags.mark_flag_as_required('project_dir')
flags.mark_flag_as_required('output_file_path')


def main(_):
  with open(FLAGS.output_file_path, 'w') as output_file:
    for bitcode_file_path in glob.glob(
        os.path.join(FLAGS.project_dir, '**/*.bc'), recursive=True):
      bitcode_file_full_path = os.path.join(FLAGS.project_dir,
                                            bitcode_file_path)
      logging.info(f'processing {bitcode_file_full_path}')
      modules_passes_ran = bitcode_module.get_passes_bitcode_module(
          bitcode_file_full_path)
      for module_passes_ran in modules_passes_ran:
        passes_ran = ','.join(
            ['1' if pass_ran else '0' for pass_ran in module_passes_ran])
        output_file.write(passes_ran + '\n')


if __name__ == '__main__':
  app.run(main)

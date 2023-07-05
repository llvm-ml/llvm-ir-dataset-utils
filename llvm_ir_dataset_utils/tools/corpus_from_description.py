"""Tool that builds a bitcode corpus from a description"""

import json
import multiprocessing

from absl import app
from absl import flags
from absl import logging
import ray

from llvm_ir_dataset_utils.builders import builder

FLAGS = flags.FLAGS

flags.DEFINE_string("corpus_description", None,
                    "The path to the JSON description file")
flags.DEFINE_string("base_dir", None,
                    "The base directory to perform the build in")
flags.DEFINE_string("corpus_dir", None, "The base directory to put the corpus")

flags.mark_flag_as_required("corpus_description")
flags.mark_flag_as_required("base_dir")
flags.mark_flag_as_required("corpus_dir")


def main(_):
  ray.init()
  with open(FLAGS.corpus_description) as corpus_description_file:
    corpus_description = json.load(corpus_description_file)
    build_future = builder.get_build_future(corpus_description, FLAGS.base_dir,
                                            FLAGS.corpus_dir,
                                            multiprocessing.cpu_count(), {})
    logging.info('Starting build.')
    ray.get(build_future)
    logging.info('Build finished.')


if __name__ == "__main__":
  app.run(main)

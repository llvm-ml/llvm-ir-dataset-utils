"""Tool that builds a bitcode corpus from a description"""

from absl import app
from absl import flags

from llvm_ir_dataset_utils.builders import builder

FLAGS = flags.FLAGS

flags.DEFINE_string("corpus_description", None,
                    "The path to the JSON description file")
flags.DEFINE_string("base_dir", None,
                    "The base directory to perform the build in")

flags.mark_flag_as_required("corpus_description")
flags.mark_flag_as_required("base_dir")


def main(_):
  builder.parse_and_build_from_description(FLAGS.corpus_description,
                                           FLAGS.base_dir)


if __name__ == "__main__":
  app.run(main)

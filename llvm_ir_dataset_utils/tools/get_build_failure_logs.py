"""Tool to find all the logs for targets that failed to build from a corpus
directory."""

import glob
import os
import json

from absl import app
from absl import flags

FLAGS = flags.FLAGS

flags.DEFINE_string('corpus_dir', None,
                    'The corpus directory to look for build logs in.')

flags.mark_flag_as_required('corpus_dir')


def main(_):
  for build_manifest_file_path in glob.glob(
      os.path.join(FLAGS.corpus_dir, '*/build_manifest.json')):
    with open(build_manifest_file_path) as build_manifest_file:
      build_manifest = json.load(build_manifest_file)
    for target in build_manifest['targets']:
      if target['success'] == False:
        print(target['name'] + ',' + target['build_log'])


if __name__ == '__main__':
  app.run(main)

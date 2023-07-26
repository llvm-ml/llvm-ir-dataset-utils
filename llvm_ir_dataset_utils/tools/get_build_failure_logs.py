"""Tool to find all the logs for targets that failed to build from a corpus
directory."""

import glob
import os
import json
import logging

from absl import app
from absl import flags

FLAGS = flags.FLAGS

flags.DEFINE_string('corpus_dir', None,
                    'The corpus directory to look for build logs in.')

flags.mark_flag_as_required('corpus_dir')


def main(_):
  build_failures = 0
  missing_logs = 0
  for build_manifest_file_path in glob.glob(
      os.path.join(FLAGS.corpus_dir, '*/build_manifest.json')):
    with open(build_manifest_file_path) as build_manifest_file:
      build_manifest = json.load(build_manifest_file)
    for target in build_manifest['targets']:
      if target['success'] == False and target['build_log'] is not None:
        print(target['name'] + ',failure,' + target['build_log'])
        build_failures += 1
      if target['build_log'] is None:
        print(target['name'] + ',no_logs,NULL')
        missing_logs += 1
  logging.warning(f'Found {build_failures} build failures.')
  logging.warning(f'{missing_logs} targets were missing logs.')


if __name__ == '__main__':
  app.run(main)

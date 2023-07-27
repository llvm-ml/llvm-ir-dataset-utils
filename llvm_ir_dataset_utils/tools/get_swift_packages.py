"""Tool for getting Swift package list."""

import subprocess
import tempfile
import logging
import json
import os

from absl import app
from absl import flags

FLAGS = flags.FLAGS

flags.DEFINE_string('package_list', 'swift_package_list.txt',
                    'The path to write the list of swift packages to.')

REGISTRY_REPOSITORY = 'https://github.com/SwiftPackageIndex/PackageList'


def main(_):
  package_list = []
  with tempfile.TemporaryDirectory() as download_dir:
    registry_path = os.path.join(download_dir, 'registry')
    registry_clone_vector = [
        'git', 'clone', REGISTRY_REPOSITORY, '--depth=1', registry_path
    ]
    logging.info('Cloning registry repository.')
    subprocess.run(
        registry_clone_vector,
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE)
    logging.info('Processing registry.')
    package_list_json_path = os.path.join(registry_path, 'packages.json')
    with open(package_list_json_path) as package_list_json_file:
      package_list = json.load(package_list_json_file)
  logging.info('Writing packages to list.')
  with open(FLAGS.package_list, 'w') as package_list_file:
    for package in package_list:
      package_list_file.write(f'{package}\n')


if __name__ == '__main__':
  app.run(main)

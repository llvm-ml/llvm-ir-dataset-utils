"""Tool for getting Julia packages."""

import glob
import subprocess
import tempfile
import os
import logging
import json

from absl import app
from absl import flags

import toml

FLAGS = flags.FLAGS

flags.DEFINE_string('package_list', 'julia_package_list.json',
                    'The path to write all the list of Julia packages to.')

REGISTRY_REPOSITORY = 'https://github.com/JuliaRegistries/General'


def main(_):
  package_list = []
  with tempfile.TemporaryDirectory() as download_dir:
    registry_path = os.path.join(download_dir, 'registry')
    repository_clone_vector = [
        'git', 'clone', REGISTRY_REPOSITORY, '--depth=1', registry_path
    ]
    logging.info('Cloning registry repository.')
    subprocess.run(
        repository_clone_vector,
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE)
    logging.info('Processing registry.')
    for package_toml_path in glob.glob(
        os.path.join(registry_path, '**/Package.toml'), recursive=True):
      with open(package_toml_path) as package_toml_file:
        package_description = toml.load(package_toml_file)
        package_name = package_description['name']
        package_repo = package_description['repo']
        if 'jll' not in package_name:
          package_list.append({'name': package_name, 'repo': package_repo})
  logging.info('Writing packages to list.')
  with open(FLAGS.package_list, 'w') as package_list_file:
    json.dump(package_list, package_list_file, indent=2)


if __name__ == '__main__':
  app.run(main)

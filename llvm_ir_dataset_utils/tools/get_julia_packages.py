"""Tool for getting Julia packages."""

import glob
import subprocess
import tempfile
import os

from absl import app
from absl import logging
from absl import flags

# TODO(boomanaiden154): Add this as a dependency to the Pipfile and regenerate
# the lock file.
import toml

FLAGS = flags.FLAGS

flags.DEFINE_string('package_list', 'julia_package_list.txt',
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
        package_list.append(package_description['name'])
  logging.info('Writing packages to list.')
  with open(FLAGS.package_list, 'w') as package_list_file:
    for package in package_list:
      package_list_file.write(f'{package}\n')


if __name__ == '__main__':
  app.run(main)

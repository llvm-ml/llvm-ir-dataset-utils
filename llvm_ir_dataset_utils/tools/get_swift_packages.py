"""Tool for getting Swift package list."""

import subprocess
import tempfile
import logging
import json
import os

from llvm_ir_dataset_utils.util import licenses

from absl import app
from absl import flags

FLAGS = flags.FLAGS

flags.DEFINE_string('package_list', 'swift_package_list.txt',
                    'The path to write the list of swift packages to.')
flags.DEFINE_string(
    'gh_pat', None,
    'Your github personal access token. Needed to query license information')

flags.mark_flag_as_required('gh_pat')

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

  logging.info('Collecting license information')
  sanitized_package_list = []
  for package in package_list:
    # We don't want the .git that is automatically at the end
    sanitized_package_list.append(package[:-4])
  repository_license_map = licenses.get_repository_licenses(
      sanitized_package_list, FLAGS.gh_pat)

  logging.info('Writing packages to list.')
  output_package_list = []
  for package in package_list:
    current_package = {
        'repo': package,
        'license': repository_license_map[package[:-4]]
    }
    output_package_list.append(current_package)
  with open(FLAGS.package_list, 'w') as package_list_file:
    json.dump(output_package_list, package_list_file, indent=2)


if __name__ == '__main__':
  app.run(main)

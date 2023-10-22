"""Tool for getting Julia packages."""

import glob
import subprocess
import tempfile
import os
import logging
import json

from llvm_ir_dataset_utils.util import licenses

from absl import app
from absl import flags

import toml

FLAGS = flags.FLAGS

flags.DEFINE_string('package_list', 'julia_package_list.json',
                    'The path to write all the list of Julia packages to.')
flags.DEFINE_string(
    'gh_pat', None,
    'Your Github personal access token. Needed to query license information.')

flags.mark_flag_as_required('gh_pat')

REGISTRY_REPOSITORY = 'https://github.com/JuliaRegistries/General'


def main(_):
  package_list = []
  repository_url_list = []
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
          # Omit the last four characters as julia includes .git by default
          # in all their repository urls which we don't want.
          repository_url_list.append(package_repo[:-4])

  logging.info('Gathering license information.')
  repo_license_map = licenses.get_repository_licenses(repository_url_list,
                                                      FLAGS.gh_pat)
  for package_dict in package_list:
    package_dict['license'] = repo_license_map[package_dict['repo'][:-4]]

  logging.info('Writing packages to list.')
  with open(FLAGS.package_list, 'w') as package_list_file:
    json.dump(package_list, package_list_file, indent=2)


if __name__ == '__main__':
  app.run(main)

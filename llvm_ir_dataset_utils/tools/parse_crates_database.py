"""A tool for downloading and parsing the crates.io database to get repositories
and corpus descriptions out.
"""

import csv
import tempfile
import os
import tarfile
import sys
import json
from urllib import request
from urllib import parse

from absl import app
from absl import flags
from absl import logging

csv.field_size_limit(sys.maxsize)

FLAGS = flags.FLAGS

flags.DEFINE_string('repository_list', 'repository_list.json',
                    'The path to write the repository list to.')
flags.DEFINE_string(
    'db_dump_archive', None,
    'The path to the database dump. Only pass a value to this flag if you '
    'don\'t want the script to download the dump itself.')


def process_git_url(git_repo_url):
  url_struct = parse.urlparse(git_repo_url)
  if url_struct.netloc == 'github.com':
    # Remove everything except for the first three components of the path
    test = '/'.join(url_struct.path.split(os.sep)[:3])
    return parse.urlunparse(url_struct._replace(path=test))
  else:
    return parse.urlunparse(url_struct)


def main(_):
  with tempfile.TemporaryDirectory() as download_dir:
    file_download_path = FLAGS.db_dump_archive
    if file_download_path is None:
      logging.info('Downloading crates.io database dump.')
      file_download_path = os.path.join(download_dir, 'db-dump.tar.gz')
      request.urlretrieve('https://static.crates.io/db-dump.tar.gz',
                          file_download_path)
      logging.info('Extracting relevant data from the downloaded tar archive.')
    else:
      logging.info('Not downloading crates.io database dump, using user '
                   'archive.')
    logging.info('Extracting relevant files from archive.')
    with tarfile.open(file_download_path) as crates_tar_archive:
      files_to_extract = {}
      for crates_file_name in crates_tar_archive.getnames():
        if 'crates.csv' in crates_file_name:
          files_to_extract['crates.csv'] = crates_file_name
        elif 'versions.csv' in crates_file_name:
          files_to_extract['versions.csv'] = crates_file_name
      for file_to_extract in files_to_extract:
        crates_tar_archive.extract(files_to_extract[file_to_extract],
                                   download_dir)
      logging.info('Parsing crates list.')
      with open(os.path.join(download_dir,
                             files_to_extract['crates.csv'])) as crates_file:
        reader = csv.DictReader(crates_file)
        crates_list = [row for row in reader]
      logging.info('Parsing versions list.')
      with open(os.path.join(
          download_dir, files_to_extract['versions.csv'])) as versions_file:
        reader = csv.DictReader(versions_file)
        versions_map = {}
        for version_entry in reader:
          if version_entry['crate_id'] not in versions_map or versions_map[
              version_entry['crate_id']] < version_entry['num']:
            versions_map[version_entry['crate_id']] = version_entry['num']
  logging.info('Writing the repository list.')
  source_list = []
  for crate in crates_list:
    crate_source_dict = {
        'repository':
            crate['repository'] if crate["repository"] != '' else None,
    }
    if crate['id'] in versions_map:
      crate_version = versions_map[crate['id']]
      crate_source_dict[
          'tar_archive'] = f'https://crates.io/api/v1/crates/{crate["name"]}/{crate_version}/download'
    else:
      crate_source_dict['tar_archive'] = None
    source_list.append(crate_source_dict)
  with open(FLAGS.repository_list, 'w') as repository_list_file:
    json.dump(source_list, repository_list_file, indent=2)


if __name__ == "__main__":
  app.run(main)

"""A tool for downloading and parsing the crates.io database to get repositories
and corpus descriptions out.
"""

import csv
import tempfile
import os
import tarfile
import sys
from urllib import request
from urllib import parse

from absl import app
from absl import flags
from absl import logging

csv.field_size_limit(sys.maxsize)

FLAGS = flags.FLAGS

flags.DEFINE_string('repository_list', 'repository_list.txt',
                    'The path to write the repository list to.')


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
    logging.info('Downloading crates.io database dump.')
    file_download_path = os.path.join(download_dir, 'db-dump.tar.gz')
    request.urlretrieve('https://static.crates.io/db-dump.tar.gz',
                        file_download_path)
    logging.info('Extracting relevant data from the downloaded tar archive.')
    with tarfile.open(file_download_path) as crates_tar_archive:
      for crates_file_name in crates_tar_archive.getnames():
        if 'data/crates.csv' in crates_file_name:
          break
      crates_tar_archive.extract(crates_file_name, download_dir)
      logging.info('Parsing CSV file.')
      with open(os.path.join(download_dir, crates_file_name)) as crates_file:
        reader = csv.DictReader(crates_file)
        crates_list = [row for row in reader]
  logging.info('Writing the repository list.')
  with open(FLAGS.repository_list, 'w') as repository_list_file:
    for crate in crates_list:
      if crate["repository"] != '':
        repository_list_file.write(process_git_url(crate["repository"]) + '\n')


if __name__ == "__main__":
  app.run(main)

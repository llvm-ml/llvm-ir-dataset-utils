"""Some utilities to deal with license information"""

import requests
import json
import logging
import os
import tempfile
import subprocess

from llvm_ir_dataset_utils.sources import git_source

GITHUB_GRAPHQL_URL = 'https://api.github.com/graphql'


def generate_repository_spdx_request(repo_index, repository_url):
  repository_parts = repository_url.split('/')
  repository_owner = repository_parts[3]
  repository_name = repository_parts[4]
  return (
      f'repo{repo_index}: repository(owner: "{repository_owner}", name: "{repository_name}") {{\n'
      '  licenseInfo {\n'
      '    spdxId\n'
      '  }\n'
      '}\n')


def get_repository_licenses(repository_list, api_token):
  if len(repository_list) > 200:
    # if the number of repositories is greater than 200, split up into
    # multiple queries.
    full_repository_license_map = {}
    start_index = 0
    while start_index < len(repository_list):
      end_index = start_index + 200
      full_repository_license_map.update(
          get_repository_licenses(repository_list[start_index:end_index],
                                  api_token))
      start_index += 200
      logging.info('Just collected license information on 200 repositories')

    return full_repository_license_map

  query_string = '{\n'

  for index, repository_url in enumerate(repository_list):
    query_string += generate_repository_spdx_request(index, repository_url)

  query_string += '}'

  query_json = {'query': query_string}
  headers = {'Authorization': f'token {api_token}'}
  api_request = requests.post(
      url=GITHUB_GRAPHQL_URL, json=query_json, headers=headers)

  license_data = json.loads(api_request.text)

  repository_license_map = {}

  if license_data['data'] is None:
    print(license_data)
    import sys
    sys.exit(0)

  for repository in license_data['data']:
    repository_index = int(repository[4:])
    repository_url = repository_list[repository_index]
    if license_data['data'][repository] is None or license_data['data'][
        repository]['licenseInfo'] is None:
      repository_license_map[repository_url] = 'NOASSERTION'
      continue
    license_id = license_data['data'][repository]['licenseInfo']['spdxId']
    repository_license_map[repository_url] = license_id

  return repository_license_map


def get_detected_license_from_dir(repo_dir):
  detector_command_line = ['license-detector', '-f', 'json', './']
  license_detector_process = subprocess.run(
      detector_command_line, cwd=repo_dir, stdout=subprocess.PIPE, check=True)
  license_info = json.loads(license_detector_process.stdout.decode('utf-8'))
  primary_project = license_info[0]
  if 'error' in primary_project:
    return 'NOASSERTION'
  licenses_matched = primary_project['matches']
  if licenses_matched[0]['confidence'] > 0.9:
    return licenses_matched[0]['license']
  return 'NOASSERTION'


def get_detected_license_from_repo(repo_url, repo_name):
  with tempfile.TemporaryDirectory() as temp_dir:
    base_dir = os.path.join(temp_dir, 'base')
    corpus_dir = os.path.join(temp_dir, 'corpus')
    os.mkdir(base_dir)
    os.mkdir(corpus_dir)
    source_status = git_source.download_source_code(repo_url, repo_name, None,
                                                    base_dir, corpus_dir)
    if source_status['success'] == False:
      return 'NOASSERTION'
    project_dir = os.path.join(base_dir, repo_name)
    return get_detected_license_from_dir(project_dir)

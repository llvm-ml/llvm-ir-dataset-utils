"""Module that parses application description, downloads source code, and invokes the correct builder"""

import json
import os
import subprocess

from absl import logging

from llvm_ir_dataset_utils.builders import cmake_builder


def download_source_code_git(repo_url, repo_name, commit_sha, base_dir):
  # If the directory already exists, we can skip downloading the source,
  # currently just assuming that the requested commit is present
  if not os.path.exists(os.path.join(base_dir, repo_name)):
    git_command_vector = ["git", "clone", repo_url]
    logging.info(f"Cloning git repository {repo_url}")
    subprocess.run(git_command_vector, cwd=base_dir)
  commit_checkout_vector = ["git", "checkout", commit_sha]
  logging.info(f"Checking out commit SHA {commit_sha}")
  subprocess.run(commit_checkout_vector, cwd=os.path.join(base_dir, repo_name))


def parse_and_build_from_description(description_file_path, base_dir):
  if not os.path.exists(base_dir):
    os.makedirs(base_dir)
  with open(description_file_path) as description_file:
    app_description = json.load(description_file)
    download_source_code_git(app_description["git_repo"],
                             app_description["repo_name"],
                             app_description["commit_sha"], base_dir)
    if app_description["build_system"] == "cmake":
      build_dir = os.path.join(base_dir,
                               app_description["repo_name"] + "-build")
      if not os.path.exists(build_dir):
        os.makedirs(build_dir)
      source_dir = os.path.join(base_dir, app_description["repo_name"])
      configure_command_vector = cmake_builder.generate_configure_command(
          os.path.join(source_dir, app_description["cmake_root"]),
          app_description["cmake_flags"])
      build_command_vector = cmake_builder.generate_build_command([])
      cmake_builder.perform_build(configure_command_vector,
                                  build_command_vector, build_dir)
    else:
      raise ValueError(
          f"Build system {app_description['build_system']} is not supported")

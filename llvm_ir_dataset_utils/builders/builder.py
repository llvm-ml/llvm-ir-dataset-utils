"""Module that parses application description, downloads source code, and invokes the correct builder"""

import os
import subprocess
import json
import pathlib
import multiprocessing
import shutil

from absl import logging
import ray

from llvm_ir_dataset_utils.builders import cmake_builder
from llvm_ir_dataset_utils.builders import manual_builder
from llvm_ir_dataset_utils.builders import autoconf_builder
from llvm_ir_dataset_utils.builders import cargo_builder


def download_source_code_git(repo_url, repo_name, commit_sha, base_dir,
                             corpus_dir):
  # If the directory already exists, we can skip downloading the source,
  # currently just assuming that the requested commit is present
  if not os.path.exists(os.path.join(base_dir, repo_name)):
    with open(os.path.join(corpus_dir, 'git.log'), 'w') as git_log_file:
      git_command_vector = ["git", "clone", repo_url]
      if commit_sha is None or commit_sha == '':
        git_command_vector.append('--depth=1')
      git_command_vector.append(repo_name)
      logging.info(f"Cloning git repository {repo_url}")
      environment = os.environ.copy()
      environment['GIT_TERMINAL_PROMPT'] = '0'
      environment['GIT_ASKPASS'] = 'echo'
      subprocess.run(
          git_command_vector,
          cwd=base_dir,
          stdout=git_log_file,
          stderr=git_log_file,
          env=environment)
      if commit_sha is not None and commit_sha != '':
        commit_checkout_vector = ["git", "checkout", commit_sha]
        logging.info(f"Checked out commit SHA {commit_sha}")
        subprocess.run(
            commit_checkout_vector,
            cwd=os.path.join(base_dir, repo_name),
            stdout=git_log_file,
            stderr=git_log_file)


def get_build_future(corpus_description,
                     base_dir,
                     corpus_dir,
                     threads,
                     extra_env_variables,
                     cleanup=False):
  return parse_and_build_from_description.options(num_cpus=threads).remote(
      corpus_description, base_dir, corpus_dir, threads, extra_env_variables,
      cleanup)


@ray.remote(num_cpus=multiprocessing.cpu_count())
def parse_and_build_from_description(corpus_description,
                                     base_dir,
                                     corpus_base_dir,
                                     threads,
                                     extra_env_variables,
                                     cleanup=False):
  corpus_dir = os.path.join(corpus_base_dir, corpus_description["repo_name"])
  pathlib.Path(corpus_dir).mkdir(exist_ok=True, parents=True)
  pathlib.Path(base_dir).mkdir(exist_ok=True)
  download_source_code_git(corpus_description["git_repo"],
                           corpus_description["repo_name"],
                           corpus_description["commit_sha"], base_dir,
                           corpus_dir)
  build_dir = os.path.join(base_dir, corpus_description["repo_name"] + "-build")
  if not os.path.exists(build_dir):
    os.makedirs(build_dir)
  source_dir = os.path.join(base_dir, corpus_description["repo_name"])
  if corpus_description["build_system"] == "cmake":
    configure_command_vector = cmake_builder.generate_configure_command(
        os.path.join(source_dir, corpus_description["cmake_root"]),
        corpus_description["cmake_flags"])
    build_command_vector = cmake_builder.generate_build_command([], threads)
    cmake_builder.perform_build(configure_command_vector, build_command_vector,
                                build_dir)
    cmake_builder.extract_ir(build_dir, corpus_dir, threads)
  elif corpus_description["build_system"] == "manual":
    manual_builder.perform_build(corpus_description["commands"], source_dir,
                                 threads)
    manual_builder.extract_ir(source_dir, corpus_dir, threads)
  elif corpus_description["build_system"] == "autoconf":
    configure_command_vector = autoconf_builder.generate_configure_command(
        source_dir, corpus_description["autoconf_flags"])
    build_command_vector = autoconf_builder.generate_build_command(threads)
    autoconf_builder.perform_build(configure_command_vector,
                                   build_command_vector, build_dir, corpus_dir)
    autoconf_builder.extract_ir(build_dir, corpus_dir, threads)
  elif corpus_description["build_system"] == "cargo":
    build_log = cargo_builder.build_all_targets(source_dir, build_dir,
                                                corpus_dir, threads,
                                                extra_env_variables)
    cargo_builder.extract_ir(build_dir, corpus_dir)
    with open(os.path.join(corpus_dir, 'build_manifest.json'),
              'w') as build_manifest:
      json.dump(build_log, build_manifest, indent=2)
  else:
    raise ValueError(
        f"Build system {corpus_description['build_system']} is not supported")
  if cleanup:
    shutil.rmtree(build_dir)
    source_dir = os.path.join(base_dir, corpus_description["repo_name"])
    if (os.path.exists(source_dir)):
      shutil.rmtree(source_dir)

"""Module that parses application description, downloads source code, and invokes the correct builder"""

import os
import json
import pathlib
import multiprocessing
import shutil
import glob

from absl import logging

import ray

from llvm_ir_dataset_utils.builders import cmake_builder
from llvm_ir_dataset_utils.builders import manual_builder
from llvm_ir_dataset_utils.builders import autoconf_builder
from llvm_ir_dataset_utils.builders import cargo_builder
from llvm_ir_dataset_utils.builders import spack_builder

from llvm_ir_dataset_utils.sources import source

from llvm_ir_dataset_utils.util import file


def get_corpus_size(corpus_dir):
  total_size = 0
  for bitcode_file in glob.glob(
      os.path.join(corpus_dir, '**/*.bc'), recursive=True):
    total_size += os.path.getsize(bitcode_file)
  return total_size


def get_build_future(corpus_description,
                     source_base_dir,
                     build_base_dir,
                     corpus_dir,
                     threads,
                     extra_env_variables,
                     extra_builder_arguments={},
                     cleanup=False):
  return parse_and_build_from_description.options(num_cpus=threads).remote(
      corpus_description,
      source_base_dir,
      build_base_dir,
      corpus_dir,
      threads,
      extra_env_variables,
      extra_builder_arguments=extra_builder_arguments,
      cleanup=cleanup)


@ray.remote(num_cpus=multiprocessing.cpu_count())
def parse_and_build_from_description(corpus_description,
                                     source_base_dir,
                                     build_base_dir,
                                     corpus_base_dir,
                                     threads,
                                     extra_env_variables,
                                     extra_builder_arguments={},
                                     cleanup=False):
  corpus_dir = os.path.join(corpus_base_dir, corpus_description["folder_name"])
  pathlib.Path(corpus_dir).mkdir(exist_ok=True, parents=True)
  pathlib.Path(source_base_dir).mkdir(exist_ok=True)
  pathlib.Path(build_base_dir).mkdir(exist_ok=True)
  source_logs = source.download_source(corpus_description['sources'],
                                       source_base_dir, corpus_dir,
                                       corpus_description['folder_name'])
  build_dir = os.path.join(build_base_dir,
                           corpus_description["folder_name"] + "-build")
  if not os.path.exists(build_dir):
    os.makedirs(build_dir)
  build_log = {}
  source_dir = os.path.join(source_base_dir, corpus_description["folder_name"])
  if corpus_description["build_system"] == "cmake":
    configure_command_vector = cmake_builder.generate_configure_command(
        os.path.join(source_dir, corpus_description["cmake_root"]),
        corpus_description["cmake_flags"])
    build_command_vector = cmake_builder.generate_build_command([], threads)
    cmake_builder.perform_build(configure_command_vector, build_command_vector,
                                build_dir, corpus_dir)
    cmake_builder.extract_ir(build_dir, corpus_dir, threads)
  elif corpus_description["build_system"] == "manual":
    manual_builder.perform_build(corpus_description["commands"], source_dir,
                                 threads, corpus_dir)
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
                                                extra_env_variables, cleanup)
    if len(build_log['targets']) == 0 and source_logs[-1]['type'] == 'git':
      logging.warn('Cargo builder detected no targets from git repository, '
                   'retrying with tar archive.')
      shutil.rmtree(source_dir)
      # The git repositry is always guaranteed to be the first source as long
      # as parse_crates_database.py was the source
      corpus_description['sources'].pop(0)
      build_future = get_build_future(corpus_description, source_base_dir,
                                      build_base_dir, corpus_base_dir, threads,
                                      extra_env_variables, cleanup)
      ray.get(build_future)
      return {}
  elif corpus_description["build_system"] == "spack":
    if 'dependency_futures' in extra_builder_arguments:
      dependency_futures = extra_builder_arguments['dependency_futures']
    else:
      dependency_futures = []
    build_log = spack_builder.build_package(
        dependency_futures, corpus_description['package_name'],
        corpus_description['package_spec'], corpus_description['package_hash'],
        corpus_dir, threads, extra_builder_arguments['buildcache_dir'],
        build_dir, cleanup)
  else:
    raise ValueError(
        f"Build system {corpus_description['build_system']} is not supported")
  if cleanup:
    file.delete_directory(build_dir, corpus_dir)
    file.delete_directory(source_dir, corpus_dir)
  build_log['sources'] = source_logs
  build_log['size'] = get_corpus_size(corpus_dir)
  with open(os.path.join(corpus_dir, 'build_manifest.json'),
            'w') as build_manifest:
    json.dump(build_log, build_manifest, indent=2)
  return build_log

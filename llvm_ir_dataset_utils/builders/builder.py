"""Module that parses application description, downloads source code, and invokes the correct builder"""

import os
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
from llvm_ir_dataset_utils.builders import spack_builder
from llvm_ir_dataset_utils.sources import source


def get_build_future(corpus_description,
                     source_base_dir,
                     build_base_dir,
                     corpus_dir,
                     threads,
                     extra_env_variables,
                     cleanup=False):
  return parse_and_build_from_description.options(num_cpus=threads).remote(
      corpus_description, source_base_dir, build_base_dir, corpus_dir, threads,
      extra_env_variables, cleanup)


@ray.remote(num_cpus=multiprocessing.cpu_count())
def parse_and_build_from_description(corpus_description,
                                     source_base_dir,
                                     build_base_dir,
                                     corpus_base_dir,
                                     threads,
                                     extra_env_variables,
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
    else:
      build_log['sources'] = source_logs
      with open(os.path.join(corpus_dir, 'build_manifest.json'),
                'w') as build_manifest:
        json.dump(build_log, build_manifest, indent=2)
  elif corpus_description["build_system"] == "spack":
    build_command_vector = spack_builder.generate_build_command(
        {}, {}, corpus_description["spack_package"])
    spack_builder.perform_build(corpus_description["spack_package"],
                                build_command_vector, corpus_dir)
    spack_builder.extract_ir(corpus_description["spack_package"], corpus_dir,
                             threads)
    if cleanup:
      spack_builder.cleanup(corpus_description["spack_package"])
  else:
    raise ValueError(
        f"Build system {corpus_description['build_system']} is not supported")
  if cleanup:
    if(os.path.exists(build_dir)):
      shutil.rmtree(build_dir)
    if (os.path.exists(source_dir)):
      shutil.rmtree(source_dir)
    if (os.path.exists(build_dir)):
      shutil.rmtree(build_dir)

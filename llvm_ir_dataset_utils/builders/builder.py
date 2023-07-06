"""Module that parses application description, downloads source code, and invokes the correct builder"""

import os
import json
import pathlib
import multiprocessing
import shutil

import ray

from llvm_ir_dataset_utils.builders import cmake_builder
from llvm_ir_dataset_utils.builders import manual_builder
from llvm_ir_dataset_utils.builders import autoconf_builder
from llvm_ir_dataset_utils.builders import cargo_builder
from llvm_ir_dataset_utils.builders import spack_builder
from llvm_ir_dataset_utils.sources import source


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
  corpus_dir = os.path.join(corpus_base_dir, corpus_description["folder_name"])
  pathlib.Path(corpus_dir).mkdir(exist_ok=True, parents=True)
  pathlib.Path(base_dir).mkdir(exist_ok=True)
  source.download_source(corpus_description['sources'], base_dir, corpus_dir,
                         corpus_description['folder_name'])
  build_dir = os.path.join(base_dir,
                           corpus_description["folder_name"] + "-build")
  if not os.path.exists(build_dir):
    os.makedirs(build_dir)
  source_dir = os.path.join(base_dir, corpus_description["folder_name"])
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
                                                extra_env_variables)
    cargo_builder.extract_ir(build_dir, corpus_dir)
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
    shutil.rmtree(build_dir)
    source_dir = os.path.join(base_dir, corpus_description["folder_name"])
    if (os.path.exists(source_dir)):
      shutil.rmtree(source_dir)

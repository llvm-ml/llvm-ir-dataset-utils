"""Module for building and extracting bitcode from applications using Portage"""

import subprocess
import os
import tempfile
import logging
import pathlib
import shutil
import re
import getpass
import ray

from mlgo.corpus import extract_ir_lib

from llvm_ir_dataset_utils.util import file
from llvm_ir_dataset_utils.util import portage as portage_utils
from llvm_ir_dataset_utils.util import extract_source_lib

SPACK_GARBAGE_COLLECTION_TIMEOUT = 300

BUILD_LOG_NAME = './portage_build.log'


def get_spec_command_vector_section(spec):
  return spec.split(' ')


def generate_emerge_command(package_to_build, threads, build_dir):
    config_root = os.path.join(build_dir, "/etc/portage")
    command_vector = [
        'emerge',  # Portage package management command
        '--jobs={}'.format(threads),  # Set the number of jobs for parallel building
        '--load-average={}'.format(threads),  # Set the maximum load average for parallel builds
        '--keep-going',  # Continue with other builds even if one fails
        '--buildpkg',  # Build binary packages, similar to Spack's build cache
        '--binpkg-respect-use=y',  # Ensure that binary package installations respect USE flag settings
        '--quiet-build=y',  # Reduce output during the build process
        package_to_build  # The package to install
    ]

    # Portage does not support setting the build directory directly in the command,
    # but this can be controlled with the PORTAGE_TMPDIR environment variable
    # This environment variable needs to be set when calling subprocess, not here directly
    return command_vector


def perform_build(package_name, assembled_build_command, corpus_dir, build_dir):
  logging.info(f"Portage building package {package_name}")
  environment = os.environ.copy()
  # Set DISTDIR and PORTAGE_TMPDIR to set the build directory for Portage
  environment['DISTDIR'] = build_dir
  environment['PORTAGE_TMPDIR'] = build_dir
  build_log_path = os.path.join(corpus_dir, BUILD_LOG_NAME)
  try:
    with open(build_log_path, 'w') as build_log_file:
      subprocess.run(
          assembled_build_command,
          stdout=build_log_file,
          stderr=build_log_file,
          check=True,
          env=environment)
  except subprocess.SubprocessError:
    logging.warn(f"Failed to build portage package {package_name}")
    return False
  logging.info(f"Finished build portage package {package_name}")
  return True


def extract_ir(corpus_dir, build_dir, threads):
  build_directory = build_dir + "/portage/"
  if build_directory is not None:
    current_verbosity = logging.getLogger().getEffectiveLevel()
    logging.getLogger().setLevel(logging.ERROR)
    objects = extract_ir_lib.load_from_directory(build_directory, corpus_dir)
    print(objects)
    relative_output_paths = extract_ir_lib.run_extraction(
        objects, threads, "llvm-objcopy", None, None, ".llvmcmd", ".llvmbc")
    print(relative_output_paths)
    extract_ir_lib.write_corpus_manifest(None, relative_output_paths,
                                         corpus_dir)
    logging.getLogger().setLevel(current_verbosity)
    extract_source_lib.copy_source(build_directory, corpus_dir)


def cleanup(package_name, package_spec, corpus_dir, uninstall=True):
  #TODO: Implement cleanup
  return


def construct_build_log(build_success, package_name):
  return {
      'targets': [{
          'name': package_name,
          'build_log': BUILD_LOG_NAME,
          'success': build_success
      }]
  }

def portage_add_local_mirror(build_dir, local_mirror_dir):
    environment = os.environ.copy()
    environment['HOME'] = build_dir
    # Create the file:// URL for the local mirror directory
    local_mirror_url = f"file://{local_mirror_dir}"
    
    # Path to the Portage make.conf file within the build directory
    make_conf_path = os.path.join(build_dir, "etc/portage/make.conf")
    
    # Ensure the make.conf file exists
    os.makedirs(os.path.dirname(make_conf_path), exist_ok=True)
    if not os.path.exists(make_conf_path):
        with open(make_conf_path, 'w') as file:
            file.write("# Generated make.conf\n")
    
    # Read and update the make.conf file
    with open(make_conf_path, 'r+') as file:
        lines = file.readlines()
        file.seek(0)
        file.truncate()
        found = False
        
        # Update the GENTOO_MIRRORS setting
        for line in lines:
            if line.startswith("GENTOO_MIRRORS="):
                line = f"GENTOO_MIRRORS=\"{local_mirror_url}\"\n"
                found = True
            file.write(line)
        
        # If GENTOO_MIRRORS was not found, add a new line
        if not found:
            file.write(f"GENTOO_MIRRORS=\"{local_mirror_url}\"\n")

def build_package(dependency_futures,
                  package_name,
                  package_spec,
                  corpus_dir,
                  threads,
                  buildcache_dir,
                  build_dir,
                  cleanup_build=False):
  dependency_futures = ray.get(dependency_futures)
  for dependency_future in dependency_futures:
    if dependency_future['targets'][0]['success'] != True:
      logging.warning(
          f'Dependency {dependency_future["targets"][0]["name"]} failed to build for package {package_name}, not building.'
      )
      if cleanup_build:
        cleanup(package_name, package_spec, corpus_dir, uninstall=False)
      return construct_build_log(False, package_name, None)
  build_command = generate_emerge_command(package_spec, threads, build_dir)
  build_result = perform_build(package_name, build_command, corpus_dir,
                               build_dir)
  if build_result:
    extract_ir(corpus_dir, build_dir, threads)
    # push_to_buildcache(package_spec, buildcache_dir, corpus_dir)
    logging.warning(f'Finished building {package_name}')
  if cleanup_build:
    if build_result:
      cleanup(package_name, package_spec, corpus_dir)
    else:
      cleanup(package_name, package_spec, corpus_dir, uninstall=False)
  return construct_build_log(build_result, package_name)

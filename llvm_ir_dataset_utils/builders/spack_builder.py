"""Module for building and extracting bitcode from applications using spack"""

import subprocess
import os
import tempfile

from absl import logging

from compiler_opt.tools import extract_ir_lib


def generate_build_command(install_options_dict, compile_options_dict,
                           package_to_build):

  # Syntax: spack install <flags> <package to build> <compiler+options>
  command_vector = [
      "spack", "install", "--keep-stage", "--overwrite", "-y",
      "--use-buildcache", "never,never,auto"
  ]

  # Provide further flags provided to the installation comand
  for option in install_options_dict:
    command_vector.append(f"{option}={install_options_dict[option]}")

  # Insert the package to build
  command_vector.append(package_to_build)

  # Default compiler configuration to allow for bitcode extraction
  # '%clang' forces the entire build chain to use LLVM compilation
  command_vector.append("%clang")
  # Providing flags for the different compilers, and linker option
  command_vector.append("cflags=\"-Xclang -fembed-bitcode=all\"")
  command_vector.append("cppflags=\"-Xclang -fembed-bitcode=all\"")

  # Provide further flags to the compilation command
  for option in compile_options_dict:
    command_vector.append(f"{option}={compile_options_dict[option]}")

  return command_vector


def perform_build(package_name, assembled_build_command, corpus_dir):
  logging.info(f"Spack building package {package_name}")
  try:
    with open(os.path.join(corpus_dir, 'spack_build.log'),
              'w') as build_log_file:
      subprocess.run(
          assembled_build_command,
          stdout=build_log_file,
          stderr=build_log_file,
          check=True)
  except:
    logging.warn(f"Failed to build spack package {package_name}")
  logging.info(f"Finished build spack package {package_name}")


def extract_ir(package_name, corpus_dir, threads):
  # TODO(boomanaiden154): It feels like tempfile.gettempdir() might be a little
  # bit flaky. Do some investigation on whether this is the case/alternatives.
  spack_build_directory = os.path.join(tempfile.gettempdir(), 'spack-stage')
  spack_stages = os.listdir(spack_build_directory)
  for spack_stage_dir in spack_stages:
    if package_name in spack_stage_dir:
      break
  # spack_stage_dir now contains the name of the directory
  build_directory = os.path.join(spack_build_directory, spack_stage_dir,
                                 'spack-src')
  objects = extract_ir_lib.load_from_directory(build_directory, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(objects, threads,
                                                        "llvm-objcopy", None,
                                                        None, ".llvmcmd",
                                                        ".llvmbc")
  extract_ir_lib.write_corpus_manifest(None, relative_output_paths, corpus_dir)


def cleanup(package_name):
  uninstall_command_vector = ["spack", "uninstall", package_name]
  subprocess.run(
      uninstall_command_vector,
      check=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE)
  clean_command_vector = ["spack", "clean", "--stage"]
  subprocess.run(
      clean_command_vector,
      check=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE)

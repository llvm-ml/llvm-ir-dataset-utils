"""Module for building and extracting bitcode from applications using autoconf"""

import os
import multiprocessing
import subprocess

from compiler_opt.tools import extract_ir_lib


def generate_configure_command(root_path, options_dict):
  command_vector = [os.path.join(root_path, "configure")]
  for option in options_dict:
    command_vector.append(f"--{option}=\"{options_dict[option]}\"")
  return command_vector


def generate_build_command():
  command_vector = ["make", f"-j{multiprocessing.cpu_count()}"]
  return command_vector


def perform_build(configure_command_vector, build_command_vector, build_dir):
  configure_env = os.environ.copy()
  configure_env["CC"] = "clang"
  configure_env["CXX"] = "clang++"
  configure_env["CFLAGS"] = "-Xclang -fembed-bitcode=all"
  configure_env["CXXFLAGS"] = "-Xclang -fembed-bitcode=all"
  configure_command = " ".join(configure_command_vector)
  subprocess.run(
      configure_command,
      cwd=build_dir,
      env=configure_env,
      check=True,
      shell=True)
  subprocess.run(build_command_vector, cwd=build_dir, check=True)


def extract_ir(build_dir, corpus_dir):
  objects = extract_ir_lib.load_from_directory(build_dir, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(
      objects, multiprocessing.cpu_count(), "llvm-objcopy", None, None,
      ".llvmcmd", ".llvmbc")
  extract_ir_lib.write_corpus_manifest(None, relative_output_paths, corpus_dir)

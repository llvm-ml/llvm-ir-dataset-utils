"""Module for building and extracting bitcode from applications using autoconf"""

import os
import subprocess

from compiler_opt.tools import extract_ir_lib


def generate_configure_command(root_path, options_dict):
  command_vector = [os.path.join(root_path, "configure")]
  for option in options_dict:
    command_vector.append(f"--{option}=\"{options_dict[option]}\"")
  return command_vector


def generate_build_command(threads):
  command_vector = ["make", f"-j{threads}"]
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


def extract_ir(build_dir, corpus_dir, threads):
  objects = extract_ir_lib.load_from_directory(build_dir, corpus_dir)
  relative_output_paths = extract_ir_lib.run_extraction(objects, threads,
                                                        "llvm-objcopy", None,
                                                        None, ".llvmcmd",
                                                        ".llvmbc")
  extract_ir_lib.write_corpus_manifest(None, relative_output_paths, corpus_dir)

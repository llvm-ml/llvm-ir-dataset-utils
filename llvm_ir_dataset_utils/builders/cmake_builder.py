"""Module for building and extracting bitcode from applications using CMake"""

import subprocess


def generate_configure_command(root_path, options_dict):
  command_vector = ["cmake", "-G", "Ninja"]
  for option in options_dict:
    command_vector.append(f"-D{option}={options_dict[option]}")
  # Add some default flags that are needed for bitcode extraction
  command_vector.append("-DCMAKE_C_COMPILER=clang")
  command_vector.append("-DCMAKE_CXX_COMPILER=clang++")
  # These two flags assume this is a stanard non-LTO build, will need to fix
  # later when we want to support (Thin)LTO builds.
  command_vector.append("-DCMAKE_C_FLAGS='-Xclang -fembed-bitcode=all'")
  command_vector.append("-DCMAKE_CXX_FLAGS='-Xclang -fembed-bitcode=all'")
  command_vector.append("-DCMAKE_EXPORT_COMPILE_COMMANDS=ON")
  command_vector.append(root_path)
  return command_vector


def generate_build_command(targets):
  command_vector = ["ninja"]
  command_vector.extend(targets)
  return command_vector


def perform_build(configure_command_vector, build_command_vector, build_dir):
  subprocess.run(configure_command_vector, cwd=build_dir, check=True)
  subprocess.run(build_command_vector, cwd=build_dir, check=True)

"""Utilities related to spack."""

import subprocess
import os


def get_spack_arch_info(info_type):
  spack_arch_command_vector = ['spack', 'arch', f'--{info_type}']
  arch_process = subprocess.run(
      spack_arch_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      check=True)
  return arch_process.stdout.decode('utf-8').rsplit()[0]


def get_compiler_version():
  compiler_command_vector = ['clang', '--version']
  compiler_version_process = subprocess.run(
      compiler_command_vector,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      check=True)
  version_line = compiler_version_process.stdout.decode('utf-8').split('\n')[0]
  version_line_parts = version_line.split(' ')
  for index, version_line_part in enumerate(version_line_parts):
    if version_line_part == 'version':
      return version_line_parts[index + 1]


def get_spack_compiler_config():
  compiler_config = (
      "compilers:\n"
      "- compiler:\n"
      f"    spec: clang@={get_compiler_version()}\n"
      "    paths:\n"
      "      cc: /usr/bin/clang\n"
      "      cxx: /usr/bin/clang++\n"
      "      f77: /usr/bin/gfortran\n"
      "      fc: /usr/bin/gfortran\n"
      "    flags:\n"
      "      cflags: -Xclang -fembed-bitcode=all\n"
      "      cxxflags: -Xclang -fembed-bitcode=all\n"
      f"    operating_system: {get_spack_arch_info('operating-system')}\n"
      "    target: x86_64\n"
      "    modules: []\n"
      "    environment: {}\n"
      "    extra_rpaths: []")
  return compiler_config


def spack_setup_compiler(build_dir):
  # TODO(boomanaiden154): The following path is variable depending upon the
  # system. For example, on some systems itis ~/.spack/linux and on others it
  # is ~/.spack/cray. We should grab this path more intelligently from spack
  # somehow.
  compiler_config_path = os.path.join(build_dir, '.spack/compilers.yaml')
  with open(compiler_config_path, 'w') as compiler_config_file:
    compiler_config_file.writelines(get_spack_compiler_config())

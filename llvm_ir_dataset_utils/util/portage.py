"""Utilities related to portage."""

import subprocess
import os

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

def get_os_info():
    import platform
    return platform.system().lower()

def get_portage_compiler_config():
    compiler_version = get_compiler_version()
    os_info = get_os_info()
    compiler_config = (
        f"# Compiler Configuration\n"
        f"CFLAGS=\"-Xclang -fembed-bitcode=all\"\n"
        f"CXXFLAGS=\"${{CFLAGS}}\"\n"
        f"FCFLAGS=\"${{CFLAGS}}\"\n"
        f"# Compiler: Clang {compiler_version}\n"
        f"# Operating System: {os_info}\n"
        "CC=\"/usr/bin/clang\"\n"
        "CXX=\"/usr/bin/clang++\"\n"
        "FC=\"/usr/bin/gfortran\"\n"
        "F77=\"/usr/bin/gfortran\"\n"
    )
    return compiler_config

def portage_setup_compiler(build_dir):
    # Same as spack, path is variable depending upon the system.
    # Path to the Portage make.conf file within the build directory
    make_conf_path = os.path.join(build_dir, "/etc/portage/make.conf")
    
    # Ensure the directory for make.conf exists
    os.makedirs(os.path.dirname(make_conf_path), exist_ok=True)
    
    # Write the compiler configuration to make.conf
    with open(make_conf_path, 'w') as compiler_config_file:
        compiler_config_file.writelines(get_portage_compiler_config())

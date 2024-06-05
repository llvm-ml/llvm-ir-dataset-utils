"""Utilities related to portage."""

import subprocess
import shutil
import os


def get_portage_compiler_config(filename):
    content = (
        'COMMON_FLAGS="-O2 -pipe -Xclang -fembed-bitcode=all"\n'
        '\n'
        'CC="/root/ir-dataset/utils/compiler_wrapper"\n'
        'CXX="/root/ir-dataset/utils/compiler_wrapper++"\n'
        'CFLAGS="${COMMON_FLAGS}"\n'
        'CXXFLAGS="${COMMON_FLAGS}"\n'
        'FCFLAGS="${COMMON_FLAGS}"\n'
        'FFLAGS="${COMMON_FLAGS}"\n'
        '\n'
        'FEATURES="noclean"\n'
        '\n'
        'LC_MESSAGES=C.utf8'
    )
    with open(filename, 'w') as file:
        file.write(content)



def portage_setup_compiler(build_dir):
  # Same as spack, path is variable depending upon the system.
  # Path to the Portage make.conf file within the build directory
  source_config_folder = '/etc/portage/'
  config_path = os.path.join(build_dir, "etc/portage")
  make_conf_path = os.path.join(config_path, "make.conf")
  make_profile_path = os.path.join(config_path, "make.profile")
  if os.path.exists(config_path):
    shutil.rmtree(config_path)
  shutil.copytree(source_config_folder, config_path)

  # Delete make.profile and make a new soft link to the default profile
  shutil.rmtree(make_profile_path)
  os.symlink('/etc/portage/make.profile', make_profile_path)
  get_portage_compiler_config(make_conf_path)

def clean_binpkg(package_spec):
  command_vector = ['rm', '-rf', '/var/cache/binpkgs/' + package_spec]
  subprocess.run(command_vector)
  sync_command = ['emaint', '--fix', 'binhost']
  subprocess.run(sync_command)
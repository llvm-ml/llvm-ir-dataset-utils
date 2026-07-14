"""Utilities related to portage."""

import os
import pathlib
import shutil


def get_compiler_wrappers():
  repository_root = pathlib.Path(__file__).resolve().parents[2]
  wrapper_directory = repository_root / 'utils'
  c_wrapper = wrapper_directory / 'compiler_wrapper'
  cxx_wrapper = wrapper_directory / 'compiler_wrapper++'

  for wrapper in (c_wrapper, cxx_wrapper):
    if not wrapper.is_file() or not os.access(wrapper, os.X_OK):
      raise FileNotFoundError(
          f'Portage compiler wrapper is missing or not executable: {wrapper}')

  return c_wrapper, cxx_wrapper


def get_portage_compiler_config(filename, c_wrapper, cxx_wrapper):

  content = (
      'COMMON_FLAGS="-O2 -pipe -Xclang -fembed-bitcode=all '
      '-Wno-implicit-function-declaration -Wno-reserved-user-defined-literal '
      '-Wno-register -Wno-error -Wno-register"\n'
      '\n'
      f'CC="{c_wrapper}"\n'
      f'CXX="{cxx_wrapper}"\n'
      'CFLAGS="${COMMON_FLAGS}"\n'
      'CXXFLAGS="${COMMON_FLAGS}"\n'
      'FCFLAGS="-O2 -pipe "\n'
      'FFLAGS="-O2 -pipe "\n'
      '\n'
      'LC_MESSAGES=C.utf8\n'
      'FEATURES="keepwork noclean -ipc-sandbox -xattr -network-sandbox '
      '-pid-sandbox -sandbox -usersandbox -usersync -userfetch -userpriv"')
  with open(filename, 'w') as file:
    file.write(content)


def portage_setup_compiler(build_dir):
  # Same as spack, path is variable depending upon the system.
  # Path to the Portage make.conf file within the build directory

  source_config_folder = '/etc/portage/'
  config_path = os.path.join(build_dir, "etc/portage")
  make_conf_path = os.path.join(config_path, "make.conf")
  make_profile_path = os.path.join(config_path, "make.profile")
  shutil.copytree(source_config_folder, config_path)

  # Delete make.profile and make a new soft link to the default profile
  shutil.rmtree(make_profile_path)

  os.symlink('/etc/portage/make.profile', make_profile_path)
  c_wrapper, cxx_wrapper = get_compiler_wrappers()
  get_portage_compiler_config(make_conf_path, c_wrapper, cxx_wrapper)

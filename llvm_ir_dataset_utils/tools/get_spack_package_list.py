"""Tool for getting all spack packages that are usable for producing LLVM
bitcode.

Note: This must be run with `spack-python` or `spack python` rather than your
default python interpreter.
"""

import json
import multiprocessing
import tempfile
import os
import pathlib

import sys

from absl import app
from absl import logging
from absl import flags

import spack.repo
import spack.environment
import spack.spec
import spack.config

FLAGS = flags.FLAGS

flags.DEFINE_string('package_list', 'package_list.json',
                    'The path to write the package list to.')
flags.DEFINE_string(
    'spack_environment', None, 'The path to an existing spack '
    'environment that has already been concretized or a path to place a new '
    'spack environment to avoid the length concretization process when running '
    'multiple times in a row.')
flags.DEFINE_string(
    'full_packages_list', None,
    'The list of packages that are initially specified to be concretized due to matching build system criteria.'
)
flags.DEFINE_string(
    'excluded_by_deps_list', None,
    'The list of packages that would have been added due to build systems '
    'rules but were excluded due to dependencies failing to concretize.')
flags.DEFINE_string(
    'selected_package_list', None,
    'The list of packages tht are going to be concretized due to matching build '
    'system criteria and not being excluded due to dependence on an excluded '
    'package or themselves being excluded.')

EXCLUDED_PACKAGES = [
    'elfutils', 'allpaths-lg', 'dyninst', 'nccl', 'bucky', 'bench',
    'clingo-bootstrap', 'cp2k', 'root', 'gpu-burn', 'hdf5-vfd-gds', 'kahip',
    'kentutils', 'arrow', 'maverick', 'mumax', 'nvcomp', 'openradioss-starter',
    'openspeedshop-utils', 'plasma', 'pdc', 'qtwebengine', 'tiled-mm', 'unblur',
    'whip', 'cbench', 'cusz', 'cutlass', 'fds', 'fujitsu-fftw', 'rodinia',
    'knem'
]


def add_concrete_package_and_all_deps(concretized_packages, spec):
  concretized_packages[spec.dag_hash()] = {
      'spec': str(spec),
      'deps': [dep_spec.dag_hash() for dep_spec in spec.dependencies()],
      'name': str(spec.package.fullname.split('.')[1])
  }
  for dep_spec in spec.dependencies():
    if dep_spec.dag_hash() not in concretized_packages:
      add_concrete_package_and_all_deps(concretized_packages, dep_spec)


def recursively_check_dependencies(package, should_include_cache):
  if package.name in should_include_cache:
    return should_include_cache[package.name]
  for dependency in package.dependencies.keys():
    if dependency in should_include_cache and not should_include_cache[
        dependency][0]:
      should_include_cache[package.name] = (False, dependency)
      return (False, dependency)
    elif dependency in EXCLUDED_PACKAGES:
      should_include_cache[package.name] = (False, dependency)
      return (False, dependency)
    else:
      # Try except here because Spack might not be able to find the package
      # (i.e., if it's a virtual package).
      try:
        dependency_pkg_class = spack.repo.path.get_pkg_class(dependency)
        dependency_pkg = dependency_pkg_class(spack.spec.Spec(dependency))
        recursive_check_result = recursively_check_dependencies(
            dependency_pkg, should_include_cache)
        if not recursive_check_result[0]:
          return (False, recursive_check_result[1])
      except:
        continue
  should_include_cache[package.name] = (True, None)
  return (True, None)


def main(_):
  logging.info('Getting packages.')
  packages = spack.repo.all_package_names(include_virtuals=True)

  concretized_packages = {}

  if not FLAGS.spack_environment or not os.path.exists(FLAGS.spack_environment):
    logging.info('Processing packages.')

    package_list = []
    should_include_cache = {}

    # The following two arrays are only used for logging purposes.
    full_package_list = []
    excluded_package_list = []

    for package in packages:
      pkg_class = spack.repo.path.get_pkg_class(package)
      # TODO(boomanaiden154): Look into other build systems that are likely to be
      # composed of c/c++ projects.
      pkg = pkg_class(spack.spec.Spec(package))
      if (pkg.build_system_class == 'CMakePackage' or
          pkg.build_system_class == 'MakefilePackage' or
          pkg.build_system_class == 'AutotoolsPackage' or
          pkg.build_system_class == 'MesonPackage'):
        full_package_list.append(pkg.name)
        to_add = True
        for excluded_package in EXCLUDED_PACKAGES:
          if pkg.name == excluded_package:
            to_add = False
            break
        if not to_add:
          continue
        recursive_check_result = recursively_check_dependencies(
            pkg, should_include_cache)
        to_add = recursive_check_result[0]
        if to_add:
          package_list.append(pkg.name)
        else:
          excluded_package_list.append((pkg.name, recursive_check_result[1]))

    # Write some logging information to the relevant files if requested.
    if FLAGS.full_packages_list is not None:
      with open(FLAGS.full_packages_list, 'w') as full_package_list_file:
        for package in full_package_list:
          full_package_list_file.write(f'{package}\n')

    if FLAGS.excluded_by_deps_list is not None:
      with open(FLAGS.excluded_by_deps_list, 'w') as excluded_by_deps_file:
        for package in excluded_package_list:
          excluded_by_deps_file.write(f'{package[0]},{package[1]}\n')

    if FLAGS.selected_package_list is not None:
      with open(FLAGS.selected_package_list, 'w') as selected_package_list_file:
        for package in package_list:
          selected_package_list_file.write(f'{package}\n')

    logging.info(f"Concretizing {len(package_list)} packages in environment")
    with tempfile.TemporaryDirectory() as tempdir:
      if FLAGS.spack_environment:
        pathlib.Path(FLAGS.spack_environment).mkdir(
            exist_ok=False, parents=True)
        env = spack.environment.create_in_dir(FLAGS.spack_environment)
      else:
        env = spack.environment.create_in_dir(tempdir)
      for package in package_list:
        env.add(spack.spec.Spec(package))
      with spack.config.override('config:build_jobs',
                                 multiprocessing.cpu_count()):
        env.unify = False
        env.concretize()
      if FLAGS.spack_environment:
        env.write()
  else:
    logging.info('Loading existing environment')
    env = spack.environment.Environment(FLAGS.spack_environment)

  logging.info('Processing concretized environment.')
  concretized_specs = env.all_specs()
  for concretized_spec in concretized_specs:
    add_concrete_package_and_all_deps(concretized_packages, concretized_spec)

  logging.info(f'Writing {len(concretized_packages)} processed specs to file.')
  with open(FLAGS.package_list, 'w') as package_list_file:
    json.dump(concretized_packages, package_list_file, indent=2)


if __name__ == '__main__':
  app.run(main)

"""Tool for getting all spack packages that are usable for producing LLVM
bitcode.

Note: This must be run with `spack-python` or `spack python` rather than your
default python interpreter.
"""

import json
import multiprocessing
import tempfile

from collections import OrderedDict

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
    'environment that has already been concretized.')

EXCLUDED_PACKAGES = [
    'abi-compliance-checker', 'allpaths-lg', 'fujitsu-fftw', 'cusz',
    'libpressio', 'openspeedshop-utils', 'unblur', 'rstudio',
    'cbtf-agronavis-gui'
]

EXCLUDED_DEPENDENCIES = ['cuda']


def add_concrete_package_and_all_deps(concretized_packages, spec):
  concretized_packages[spec.dag_hash()] = {
      'spec': str(spec),
      'deps': [dep_spec.dag_hash() for dep_spec in spec.dependencies()],
      'name': str(spec.package.fullname.split('.')[1])
  }
  for dep_spec in spec.dependencies():
    add_concrete_package_and_all_deps(concretized_packages, dep_spec)


def main(_):
  logging.info('Getting packages.')
  packages = spack.repo.all_package_names(include_virtuals=True)

  concretized_packages = {}

  if not FLAGS.spack_environment:
    logging.info('Processing packages.')

    package_list = []

    for package in packages:
      pkg_class = spack.repo.path.get_pkg_class(package)
      # TODO(boomanaiden154): Look into other build systems that are likely to be
      # composed of c/c++ projects.
      pkg = pkg_class(spack.spec.Spec(package))
      if (pkg.build_system_class == 'CMakePackage' or
          pkg.build_system_class == 'MakefilePackage' or
          pkg.build_system_class == 'AutotoolsPackage' or
          pkg.build_system_class == 'MesonPackage'):
        for excluded_dep in EXCLUDED_DEPENDENCIES:
          if excluded_dep in pkg.dependencies.keys():
            continue
        package_list.append(pkg.name)

    with tempfile.TemporaryDirectory() as tempdir:
      env = spack.environment.create_in_dir(tempdir)
      package_list = ['3dtk']
      for package in package_list:
        env.add(spack.spec.Spec(package))
      env.concretize()
  else:
    logging.info('Loading existing environment')
    env = spack.environment.Environment(FLAGS.spack_environment)

  concretized_specs = env.all_specs()
  add_concrete_package_and_all_deps(concretized_packages, concretized_specs[0])

  with open(FLAGS.package_list, 'w') as package_list_file:
    json.dump(concretized_packages, package_list_file, indent=2)


if __name__ == '__main__':
  app.run(main)

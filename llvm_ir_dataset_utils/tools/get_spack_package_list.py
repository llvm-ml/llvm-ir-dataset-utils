"""Tool for getting all spack packages that are usable for producing LLVM
bitcode.

Note: This must be run with `spack-python` or `spack python` rather than your
default python interpreter.
"""

from absl import app
from absl import logging
from absl import flags

import spack.repo

FLAGS = flags.FLAGS

flags.DEFINE_string('package_list', 'package_list.txt',
                    'The path to write the package list to.')


def main(_):
  logging.info('Getting packages.')
  packages = spack.repo.all_package_names(include_virtuals=True)

  output_package_list = []

  logging.info('Filtering packages.')
  for package in packages:
    pkg_class = spack.repo.path.get_pkg_class(package)
    # TODO(boomanaiden154): Look into other build systems that are likely to be
    # composed of c/c++ projects.
    pkg = pkg_class(spack.spec.Spec(package))
    if (pkg.build_system_class == 'CMakePackage' or
        pkg.build_system_class == 'MakefilePackage' or
        pkg.build_system_class == 'AutotoolsPackage' or
        pkg.build_system_class == 'MesonPackage'):
      output_package_list.append(pkg.name)

  logging.info('Writing filtered packages to file.')
  with open(FLAGS.package_list, 'w') as package_list_file:
    for package in output_package_list:
      package_list_file.write(f'{package}\n')


if __name__ == '__main__':
  app.run(main)

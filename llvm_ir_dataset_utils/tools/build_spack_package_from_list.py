"""A tool for building individual spack packages or an entire list from a list
of spack packages and their dependencies.
"""

import json
import os
import pathlib

from absl import app
from absl import flags
from absl import logging

import ray

from llvm_ir_dataset_utils.builders import spack_builder

FLAGS = flags.FLAGS

flags.DEFINE_string('package_list', None, 'The list of spack packages and '
                    'their dependencies.')
flags.DEFINE_string('package_name', None, 'The name of an individual package '
                    'to build.')
flags.DEFINE_string('corpus_dir', None, 'The path to the corpus.')

flags.mark_flag_as_required('package_list')
flags.mark_flag_as_required('corpus_dir')


@ray.remote
def build_package(dependency_futures, package, corpus_dir):
  dependency_futures = ray.get(dependency_futures)
  for dependency_future in dependency_futures:
    if dependency_future != True:
      logging.warning(
          f'Some dependencies failed to build for package {package["name"]}, not building.'
      )
      return False
  build_command = spack_builder.generate_build_command(package['spec'])
  build_result = spack_builder.perform_build(package['name'], build_command,
                                             corpus_dir)
  if build_result:
    spack_builder.push_to_buildcache(package['spec'])
    spack_builder.cleanup(package['spec'], corpus_dir)
    spack_builder.extract_ir(package['name'], corpus_dir, 16)
    logging.warning(f'Finished building {package["name"]}')
  return build_result


def get_package_future(package_dict, current_package_futures, package):
  if package in current_package_futures:
    return current_package_futures[package]
  dependency_futures = []
  for dependency in package_dict[package]['deps']:
    if dependency in current_package_futures:
      dependency_futures.append(current_package_futures[dependency])
    else:
      dependency_futures.append(
          get_package_future(package_dict, current_package_futures, dependency))
  corpus_dir = os.path.join(FLAGS.corpus_dir, package_dict[package]['name'])
  pathlib.Path(corpus_dir).mkdir(parents=True, exist_ok=True)
  build_future = build_package.remote(dependency_futures, package_dict[package],
                                      corpus_dir)
  current_package_futures[package] = build_future
  return build_future


def main(_):
  with open(FLAGS.package_list) as package_list_file:
    package_dict = json.load(package_list_file)

  ray.init()
  build_futures = []
  build_futures_dict = {}

  if FLAGS.package_name:
    package = None
    for package in package_dict:
      if package_dict[package]['name'] == FLAGS.package_name:
        break
    if package is None:
      raise ValueError('At least one package must be specified to be built.')
    build_future = get_package_future(package_dict, build_futures_dict, package)
  else:
    for package in package_dict:
      build_future = get_package_future(package_dict, build_futures_dict,
                                        package)
      build_futures.append(build_future)
      build_futures_dict[package] = build_future

  ray.get(build_future)


if __name__ == '__main__':
  app.run(main)


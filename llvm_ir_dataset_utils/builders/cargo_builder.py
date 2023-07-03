"""Module for building and extracting bitcode from applications using cargo"""

import subprocess
import os
import json

from absl import logging

from compiler_opt.tools import make_corpus_lib


def get_targets_from_manifest(source_dir):
  command_vector = ["cargo", "metadata", "--no-deps"]
  try:
    # TODO(boomanaiden154): Dump the stderr of the metadata command to a log
    # somewhere
    with subprocess.Popen(
        command_vector,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=source_dir) as process:
      out, err = process.communicate()
      manifest = json.loads(out.decode("utf-8"))
    targets = []
    for package in manifest["packages"]:
      for target in package["targets"]:
        targets.append({
            "name": target["name"],
            "kind": target["kind"][0],
            "package": package["name"],
            "version": package["version"]
        })
    return targets
  except:
    return []


def get_build_log_path(corpus_dir, target):
  return os.path.join(corpus_dir,
                      target['name'] + '.' + target['kind'] + '.build.log')


def build_all_targets(source_dir, build_dir, corpus_dir):
  targets_list = get_targets_from_manifest(source_dir)
  build_log = {'targets': []}
  for target in targets_list:
    build_success = perform_build(source_dir, build_dir, corpus_dir, target)
    build_log['targets'].append({
        'success': build_success,
        'build_log': get_build_log_path(corpus_dir, target),
        'name': target['name'] + '.' + target['kind']
    })
  return build_log


def perform_build(source_dir, build_dir, corpus_dir, target) -> bool:
  logging.info(
      f"Building target {target['name']} of type {target['kind']} from package {target['package']}"
  )
  build_env = os.environ.copy()
  build_env["CARGO_TARGET_DIR"] = build_dir
  build_command_vector = [
      "cargo", "rustc", "--all-features", "-p",
      f"{target['package']}@{target['version']}"
  ]
  if target['kind'] == "lib":
    build_command_vector.append("--lib")
  elif target['kind'] == "test":
    build_command_vector.extend(["--test", target['name']])
  elif target['kind'] == "bench":
    build_command_vector.extend(["--bench", target['name']])
  elif target['kind'] == "bin":
    build_command_vector.extend(["--bin", target['name']])
  elif target['kind'] == "example":
    build_command_vector.extend(["--example", target['name']])
  else:
    logging.warn("Unrecognized target type, not building.")
    return False
  build_command_vector.extend(["--", '--emit=llvm-bc'])
  try:
    with open(get_build_log_path(corpus_dir, target), 'w') as build_log_file:
      subprocess.run(
          build_command_vector,
          cwd=source_dir,
          env=build_env,
          check=True,
          stdout=build_log_file,
          stderr=build_log_file)
  except Exception as e:
    logging.warn(
        f"Failed to build target {target['name']} of type {target['kind']} from package {target['package']}"
    )
    return False
  logging.info(
      f"Finished building target {target['name']} of type {target['kind']} from package {target['package']}"
  )
  return True


def extract_ir(build_dir, corpus_dir):
  # TODO(boomanaiden154): Look into getting a build manifest from cargo.
  relative_paths = make_corpus_lib.load_bitcode_from_directory(build_dir)
  make_corpus_lib.copy_bitcode(relative_paths, build_dir, corpus_dir)
  make_corpus_lib.write_corpus_manifest(relative_paths, corpus_dir, '')

"""Module for building and extracting bitcode from applications using cargo"""

import subprocess
import os
import pathlib
import json

from absl import logging

from compiler_opt.tools import make_corpus_lib


def get_targets_from_manifest(source_dir):
  command_vector = ["cargo", "metadata", "--no-deps"]
  try:
    with subprocess.Popen(
        command_vector, stdout=subprocess.PIPE, cwd=source_dir) as process:
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


def build_all_targets(source_dir, build_dir):
  targets_list = get_targets_from_manifest(source_dir)
  for target in targets_list:
    logging.info(
        f"Building target {target['name']} of type {target['kind']} from package {target['package']}"
    )
    perform_build(source_dir, build_dir, target)
    logging.info(
        f"Finished building target {target['name']} of type {target['kind']} from package {target['package']}"
    )


def perform_build(source_dir, build_dir, target):
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
    return
  build_command_vector.extend(["--", '--emit=llvm-bc'])
  try:
    subprocess.run(
        build_command_vector,
        cwd=source_dir,
        env=build_env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
  except:
    logging.warn(
        f"Failed to build target {target['name']} of type {target['kind']} from package {target['package']}"
    )


def extract_ir(build_dir, corpus_dir):
  # TODO(boomanaiden154): Look into getting a build manifest from cargo.
  relative_paths = make_corpus_lib.load_bitcode_from_directory(build_dir)
  make_corpus_lib.copy_bitcode(relative_paths, build_dir, corpus_dir)
  pathlib.Path(corpus_dir).mkdir(exist_ok=True, parents=True)
  make_corpus_lib.write_corpus_manifest(relative_paths, corpus_dir, '')

"""Module for building and extracting bitcode from applications using cargo"""

import subprocess
import os
import pathlib
import json

from absl import logging

from compiler_opt.tools import make_corpus_lib


def get_targets_from_manifest(source_dir):
  command_vector = ["cargo", "read-manifest"]
  try:
    with subprocess.Popen(
        command_vector, stdout=subprocess.PIPE, cwd=source_dir) as process:
      out, err = process.communicate()
      manifest = json.loads(out.decode("utf-8"))
    targets = manifest["targets"]
    target_tuples = []
    for target in targets:
      target_tuples.append((target["kind"][0], target["name"]))
    return target_tuples
  except:
    return []


def build_all_targets(source_dir, build_dir):
  targets_list = get_targets_from_manifest(source_dir)
  for target in targets_list:
    logging.info(f"Building target {target[1]} of type {target[0]}")
    perform_build(source_dir, build_dir, target)
    logging.info(f"Finished building target {target[1]} of type {target[0]}")


def perform_build(source_dir, build_dir, target):
  build_env = os.environ.copy()
  build_env["CARGO_TARGET_DIR"] = build_dir
  build_command_vector = ["cargo", "rustc", "--all-features"]
  if target[0] == "lib":
    build_command_vector.append("--lib")
  elif target[0] == "test":
    build_command_vector.extend(["--test", target[1]])
  elif target[0] == "bench":
    build_command_vector.extend(["--bench", target[1]])
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
    logging.warn(f"Failed to build target {target[1]} of type {target[0]}")


def extract_ir(build_dir, corpus_dir):
  # TODO(boomanaiden154): Look into getting a build manifest from cargo.
  relative_paths = make_corpus_lib.load_bitcode_from_directory(build_dir)
  make_corpus_lib.copy_bitcode(relative_paths, build_dir, corpus_dir)
  pathlib.Path(corpus_dir).mkdir(exist_ok=True, parents=True)
  make_corpus_lib.write_corpus_manifest(relative_paths, corpus_dir, '')

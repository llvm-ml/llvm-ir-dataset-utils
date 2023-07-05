"""Tool to build a crate given just a repository."""

from absl import app
from absl import flags
from absl import logging
import ray

from llvm_ir_dataset_utils.builders import builder

FLAGS = flags.FLAGS

flags.DEFINE_string('repository', None, 'The repository url to clone from.')
flags.DEFINE_string('repository_list', None,
                    'Path to a file containing a list of repositories.')
flags.DEFINE_string(
    'base_dir', None,
    'The base directory to clone the source into and perform the build in.')
flags.DEFINE_string('corpus_dir', None, 'The directory to place the corpus in.')
flags.DEFINE_integer('thread_count', 8,
                     'The number of threads to use per crate build.')
flags.DEFINE_string('cargo_home', '/cargo', 'The default cargo directory.')
flags.DEFINE_string('rustup_home', '/rustup',
                    'The default rustup home directory.')

flags.mark_flag_as_required('base_dir')
flags.mark_flag_as_required('corpus_dir')


@flags.multi_flags_validator(
    ['repository', 'repository_list'],
    message=(
        'Expected one and only one of --repository and --repository_list to be'
        'defined.'),
)
def _validate_input_columns(flags_dict):
  both_defined = flags_dict['repository'] is not None and flags_dict[
      'repository_list'] is not None
  neither_defined = flags_dict['repository'] is None and flags_dict[
      'repository_list'] is None
  return not both_defined and not neither_defined


def main(_):
  ray.init()
  crates_list = []
  if FLAGS.repository is not None:
    crates_list.append(FLAGS.repository)
  elif FLAGS.repository_list is not None:
    with open(FLAGS.repository_list) as repository_list_file:
      crates_list = repository_list_file.read().splitlines()

  build_futures = []
  for index, crate_to_build in enumerate(crates_list):
    corpus_description = {
        'git_repo': crate_to_build,
        'repo_name': f'build-{index}',
        'commit_sha': '',
        'build_system': 'cargo'
    }

    additional_build_env_variables = {
        'RUSTUP_HOME': FLAGS.rustup_home,
        'CARGO_HOME': FLAGS.cargo_home
    }

    build_futures.append(
        builder.get_build_future(
            corpus_description,
            FLAGS.base_dir,
            FLAGS.corpus_dir,
            FLAGS.thread_count,
            additional_build_env_variables,
            cleanup=True))

  all_finished = []
  while len(build_futures) > 0:
    finished, build_futures = ray.wait(build_futures, timeout=5.0)
    finished_data = ray.get(finished)
    all_finished.extend(finished_data)
    logging.info(
        f'Just finished {len(finished_data)}, {len(all_finished)} done, {len(build_futures)} remaining'
    )


if __name__ == '__main__':
  app.run(main)

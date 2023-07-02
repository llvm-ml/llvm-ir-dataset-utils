"""Tool to build a crate given just a repository."""

from absl import app
from absl import flags

from llvm_ir_dataset_utils.builders import builder

FLAGS = flags.FLAGS

flags.DEFINE_string('repository', None, 'The repository url to clone from.')
flags.DEFINE_string('repository_list', None,
                    'Path to a file containing a list of repositories.')
flags.DEFINE_string(
    'base_dir', None,
    'The base directory to clone the source into and perform the build in.')
flags.DEFINE_string('corpus_dir', None, 'The directory to place the corpus in.')

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
  crates_list = []
  if FLAGS.repository is not None:
    crates_list.append(FLAGS.repository)
  elif FLAGS.repository_list is not None:
    with open(FLAGS.repository_list) as repository_list_file:
      crates_list = repository_list_file.read().splitlines()

  for index, crate_to_build in enumerate(crates_list):
    corpus_description = {
        'git_repo': crate_to_build,
        'repo_name': f'build-{index}',
        'commit_sha': '',
        'build_system': 'cargo'
    }

    builder.parse_and_build_from_description(corpus_description, FLAGS.base_dir,
                                             FLAGS.corpus_dir)


if __name__ == '__main__':
  app.run(main)

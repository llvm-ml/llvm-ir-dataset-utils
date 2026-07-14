import pytest

from llvm_ir_dataset_utils.builders import portage_builder


def test_generate_emerge_command_rebuilds_target_from_source():
  command = portage_builder.generate_emerge_command('dev-libs/boost', 8,
                                                    '/data/build/boost')

  exclude_index = command.index('--usepkg-exclude')
  assert command[exclude_index + 1] == 'dev-libs/boost'
  assert command[-1] == 'dev-libs/boost'
  assert '--usepkg' in command


def test_get_package_work_directory_selects_only_target(tmp_path):
  target_work_directory = (
      tmp_path / 'portage' / 'dev-libs' / 'boost-1.90.0-r1' / 'work')
  target_work_directory.mkdir(parents=True)
  dependency_work_directory = (
      tmp_path / 'portage' / 'dev-libs' / 'boost-build-1.90.0' / 'work')
  dependency_work_directory.mkdir(parents=True)

  result = portage_builder.get_package_work_directory(
      '=dev-libs/boost-1.90.0-r1', 'boost', tmp_path)

  assert result == target_work_directory


def test_get_package_work_directory_rejects_ambiguous_target(tmp_path):
  for version in ('1.89.0', '1.90.0-r1'):
    (tmp_path / 'portage' / 'dev-libs' / f'boost-{version}' /
     'work').mkdir(parents=True)

  with pytest.raises(RuntimeError, match='Expected one Portage work directory'):
    portage_builder.get_package_work_directory('dev-libs/boost', 'boost',
                                               tmp_path)


def test_get_package_work_directory_requires_category(tmp_path):
  with pytest.raises(ValueError, match='must contain a category'):
    portage_builder.get_package_work_directory('boost', 'boost', tmp_path)

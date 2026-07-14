import shutil
import subprocess

import pytest

from llvm_ir_dataset_utils.builders import portage_builder
from llvm_ir_dataset_utils.util import portage


def test_portage_configuration_smoke(tmp_path):
  command = portage_builder.generate_emerge_command('dev-libs/boost', 8,
                                                    tmp_path)
  exclude_index = command.index('--usepkg-exclude')
  assert command[exclude_index + 1] == 'dev-libs/boost'
  assert '--oneshot' in command
  assert '--autounmask-write=y' not in command

  make_conf = tmp_path / 'make.conf'
  make_conf.write_text('ACCEPT_LICENSE="@FREE"\nFEATURES="sandbox userpriv"\n')
  portage.get_portage_compiler_config(make_conf, '/wrapper/cc', '/wrapper/cxx')
  content = make_conf.read_text()
  assert 'ACCEPT_LICENSE="@FREE"' in content
  assert 'FEATURES="${FEATURES} keepwork noclean"' in content
  assert '-sandbox' not in content
  assert '-userpriv' not in content


def test_compiler_wrappers_smoke(tmp_path):
  if not all(shutil.which(compiler) for compiler in ('clang', 'clang++')):
    pytest.skip('clang and clang++ are required')

  c_wrapper, cxx_wrapper = portage.get_compiler_wrappers()
  cases = (
      (c_wrapper, 'input', '-x', 'c', 'int main(void) { return 0; }'),
      (cxx_wrapper, 'input.C', None, None,
       '#include <iostream>\nint main() { std::cout << "ok"; }'),
  )
  for wrapper, name, language_flag, language, source_text in cases:
    source = tmp_path / name
    output = tmp_path / f'{name}.out'
    source.write_text(source_text)
    command = [str(wrapper)]
    if language_flag:
      command.extend((language_flag, language))
    command.extend((str(source), f'-o{output}'))

    result = subprocess.run(command, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert (tmp_path / f'{name}.out.source').is_file()
    assert (tmp_path / f'{name}.out.preprocessed_source').is_file()

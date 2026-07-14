import os

from llvm_ir_dataset_utils.util import portage


def test_compiler_wrappers_are_regular_executables():
  c_wrapper, cxx_wrapper = portage.get_compiler_wrappers()

  for wrapper in (c_wrapper, cxx_wrapper):
    assert wrapper.is_file()
    assert not wrapper.is_symlink()
    assert os.access(wrapper, os.X_OK)


def test_compiler_config_uses_checkout_wrapper_paths(tmp_path):
  c_wrapper, cxx_wrapper = portage.get_compiler_wrappers()
  make_conf = tmp_path / 'make.conf'

  portage.get_portage_compiler_config(make_conf, c_wrapper, cxx_wrapper)

  content = make_conf.read_text()
  assert f'CC="{c_wrapper}"' in content
  assert f'CXX="{cxx_wrapper}"' in content
  assert '/data/ir-llvm' not in content
  assert '/tmp/llvm-ir-dataset-utils' not in content

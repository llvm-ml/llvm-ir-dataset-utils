# Building C++ corpora with Gentoo Portage

This workflow is supported inside a disposable or dedicated Gentoo container.
Do not run it directly on a workstation or production Gentoo host. Run all
commands as root inside the container because Portage installs build
dependencies and the requested package into the container's root filesystem.

The repository may be mounted at any absolute path. The Portage builder locates
`utils/compiler_wrapper` and `utils/compiler_wrapper++` from the checkout at
runtime and writes those paths into its temporary `make.conf`.

## Prerequisites

The Gentoo environment needs:

- a populated `/var/db/repos/gentoo` Portage repository;
- Python 3.9 or 3.10, as required by `pyproject.toml`;
- `clang`, `clang++`, and `llvm-objcopy` from the same LLVM release;
- the Python dependencies installed from this repository;
- enough free space for Portage work directories and the resulting corpus.

Verify the environment before starting a large build:

```bash
command -v emerge
command -v clang
command -v clang++
command -v llvm-objcopy
python3 --version
```

From the repository root, install the project in editable mode:

```bash
python3 -m pip install -e .
```

The checked-in compiler wrapper entry points are regular executable files. No
symlink setup or fixed checkout path is required.

## Portage configuration and isolation

The container is the system-isolation boundary. The builder deliberately keeps
`ROOT=/` so Portage can use the container's installed toolchain and build
dependencies; pointing `ROOT` and `SYSROOT` at an empty directory would require
bootstrapping a separate Gentoo system.

For each package, the builder copies `/etc/portage` into its build directory and
uses that copy as `PORTAGE_CONFIGROOT`. It preserves the container's selected
profile, `make.conf`, mirrors, licenses, USE settings, and package configuration,
then appends the Clang wrapper settings. Existing Portage security features such
as sandbox and userpriv are preserved. Only `keepwork` and `noclean` are added so
the target work tree remains available for IR extraction.

The emerge operation uses `--oneshot`, so the target is not added to the
container's world set. It does not automatically unmask packages or accept USE,
keyword, mask, or license changes. If dependency resolution fails, update the
appropriate file under the container's `/etc/portage`, inspect the failure, and
run the command again. The next run copies the updated configuration.

## Compiler wrapper behavior

The C and C++ entry points select `clang` and `clang++` respectively. They
understand common C/C++ suffixes, explicit `-x c`/`-x c++`, joined or separated
`-o`, and Clang response files. Multiple source inputs receive distinct capture
names instead of overwriting each other.

The real compiler runs first and its exit status is authoritative. Source or
preprocessor capture failures are reported as `compiler_wrapper:` warnings but
do not turn a successful compilation into a failed package build. Capture is
performed only for invocations with an explicit output option.

## Container mounts

Use an existing Gentoo image that already has the prerequisites above. Mount
both the repository and a persistent data directory into the container:

```bash
mkdir -p gentoo-data

docker run --rm -it \
  -v "$PWD":/workspace/llvm-ir-dataset-utils \
  -v "$PWD/gentoo-data":/data \
  -w /workspace/llvm-ir-dataset-utils \
  <prepared-gentoo-image> \
  /bin/bash
```

Podman accepts the same mount layout. The repository mount must remain visible
for the whole build because Portage invokes the wrappers from that checkout.

The official `gentoo/stage3` and `gentoo/portage` images can be used to prepare
such an image, but the current project still requires Python 3.9 or 3.10. Do not
assume that a newly published stage3 image contains a compatible Python slot.

## Corpus description

A Portage description does not download sources itself; Portage obtains them
from the selected ebuild. `package_name` must be the package name (`PN`), while
`package_spec` is the Portage atom passed to emerge.

Example for Boost:

```json
{
  "sources": [],
  "folder_name": "boost-1.90.0-r1",
  "build_system": "portage",
  "package_name": "boost",
  "package_spec": "=dev-libs/boost-1.90.0-r1",
  "license": "Boost-1.0"
}
```

Prefer an exact atom when producing a dataset that needs to be repeatable. The
selected version must exist in the mounted Portage repository and be accepted
by its keyword, mask, license, and USE configuration.

## Run one package

The repository contains `corpus_descriptions_test/portage_boost.json` as a
simple example. Run the builder from the repository root:

```bash
python3 ./llvm_ir_dataset_utils/tools/corpus_from_description.py \
  --source_dir=/data/source \
  --corpus_dir=/data/corpus \
  --build_dir=/data/build \
  --corpus_description=./corpus_descriptions_test/portage_boost.json \
  --thread_count="$(nproc)"
```

For a custom exact-version description, replace the value of
`--corpus_description` with its path.

The emerge command may use binary packages for dependencies, but it excludes
the requested target atom from binary-package selection. The target is
therefore rebuilt from source through the Clang wrappers. IR extraction is
restricted to the target package's Portage `work` directory; dependency build
directories are not included in its corpus.

By default the build directory is retained for inspection. Pass `--cleanup` to
remove it after either success or failure. A successful emerge with no extracted
LLVM IR modules is recorded as a failed corpus build.

## Outputs and checks

For a description whose `folder_name` is `boost`, the main outputs are:

```text
/data/corpus/boost/
  build_manifest.json
  portage_build.log
  *.bc and extracted source files
```

The exact corpus layout below that directory follows the object paths found in
the target package's Portage work directory. After the command finishes, check
the manifest and confirm that bitcode was produced:

```bash
sed -n '1,200p' /data/corpus/boost/build_manifest.json
find /data/corpus/boost -type f -name '*.bc' | head
```

On failure, inspect:

```bash
sed -n '1,240p' /data/corpus/boost/portage_build.log
```

The builder installs the target and dependencies into the Gentoo container's
root filesystem. Discard or reset the container when the build batch is done.

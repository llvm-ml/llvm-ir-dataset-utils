# Building Corpora

### Building a corpus from an individual description

To build a corpus from an individual description, run the following command from
the root directory of this repoistory:

```bash
PYTHONPATH="./" python3 ./llvm_ir_dataset_utils/tools/corpus_from_description.py \
  --base_dir=<path to build> \
  --corpus_description=<path to corpus description json>
```

**NOTE:** This currently doesn't create a corpus of IR but rather just builds
a corpus so that all the necessary assumptions for corpus extraction are met
(namely a `compile_commands.json`/equivalent and compilation is performed with
``-Xclang -fembed-bitcode=all`). Actual corpus extraction should be coming very
soon.

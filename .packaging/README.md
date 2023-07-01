# Packaging

This directory contains utilities to package the project along with relevant
dependencies and toolchains to build the dataset.

### Building the Docker Image

To build the Docker image, run the following command from the root of the
repository:

```bash
docker build -t llvm-ir-dataset-utils -f ./.packaging/Dockerfile .
```

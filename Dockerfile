FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
  python3 \
  python-is-python3 \
  wget \
  curl \ 
  lsb-release \ 
  software-properties-common \
  gnupg \
  python3-pip \
  git \
  pkg-config \
  libssl-dev
RUN curl https://sh.rustup.rs | sh -s -- -y --default-toolchain none
ENV PATH="$PATH:/root/.cargo/bin"
RUN rustup toolchain install nightly-2023-06-22 && \
  rustup component add rust-src rustc-dev llvm-tools-preview
RUN echo "deb http://apt.llvm.org/jammy/ llvm-toolchain-jammy-16 main" >> /etc/apt/sources.list && \
  echo "deb-src http://apt.llvm.org/jammy/ llvm-toolchain-jammy-16 main" >> /etc/apt/sources.list && \
  curl https://apt.llvm.org/llvm-snapshot.gpg.key | apt-key add -
RUN apt-get update && apt-get install -y clang-16 llvm-16 && \
  ln -s /usr/bin/clang-16 /usr/bin/clang && \
  ln -s /usr/bin/clang++-16 /usr/bin/clang++ && \
  ln -s /usr/bin/llvm-objcopy-16 /usr/bin/llvm-objcopy
COPY ./Pipfile /llvm-ir-dataset-utils/Pipfile
WORKDIR /llvm-ir-dataset-utils
RUN pip3 install pipenv && pipenv lock && pipenv sync --system
COPY . .


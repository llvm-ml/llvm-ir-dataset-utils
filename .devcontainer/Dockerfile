ARG UBUNTU_VERSION=22.04
ARG LLVM_VERSION=16

FROM ubuntu:$UBUNTU_VERSION

ARG LLVM_VERSION

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y python3 python-is-python3 wget curl lsb-release ca-certificates software-properties-common gnupg2 python3-pip git pkg-config libssl-dev

# Can this be converted into a native Ubuntu install as in the LLVM case
RUN curl https://sh.rustup.rs | sh -s -- -y --default-toolchain none
ENV PATH="$PATH:/root/.cargo/bin"
RUN rustup toolchain install nightly-2023-06-22 \
    && rustup component add rust-src rustc-dev llvm-tools-preview

RUN apt-get -q update \
    && curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key|apt-key add - \
    && apt-add-repository "deb http://apt.llvm.org/`lsb_release -cs`/ llvm-toolchain-`lsb_release -cs`-$LLVM_VERSION main" || true \
    && apt-get -q update \
    && apt-get install -y clang-$LLVM_VERSION llvm-$LLVM_VERSION llvm-$LLVM_VERSION-dev \
    && ln -s /usr/bin/clang-$LLVM_VERSION /usr/bin/clang \
    && ln -s /usr/bin/clang++-$LLVM_VERSION /usr/bin/clang++ \
    && ln -s /usr/bin/llvm-objcopy-$LLVM_VERSION /usr/bin/llvm-objcopy

RUN apt-get autoremove -y --purge \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

ENV DEBIAN_FRONTEND=
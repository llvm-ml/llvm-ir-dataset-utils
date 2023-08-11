ARG UBUNTU_VERSION=22.04
ARG LLVM_VERSION=17
ARG JULIA_MAJOR_VERSION=8
ARG JULIA_MINOR_VERSION=3
ARG SWIFT_MAJOR_VERSION=8
ARG SWIFT_MINOR_VERSION=1
ARG CUSTOM_CERT
ARG ENABLE_LEGACY_RENEGOTIATION

FROM ubuntu:$UBUNTU_VERSION

ARG LLVM_VERSION
ARG JULIA_MAJOR_VERSION
ARG JULIA_MINOR_VERSION
ARG SWIFT_MAJOR_VERSION
ARG SWIFT_MINOR_VERSION
ARG CUSTOM_CERT
ARG ENABLE_LEGACY_RENEGOTIATION

ENV DEBIAN_FRONTEND=noninteractive

# Install the base dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 \
  python3-dev \
  python-is-python3 \
  wget \
  curl \
  lsb-release \
  ca-certificates \
  software-properties-common \
  build-essential \
  gnupg2 \
  python3-pip \
  git \
  pkg-config \
  libssl-dev \
  gcc \
  gfortran \
  vim \
  libarchive-dev \
  libudev-dev \
  libasound2-dev \
  libzmq3-dev \
  cmake \
  ninja-build \
  flex \
  bison \
  libelf-dev \
  bc \
  cpio \
  htop \
  jq \
  file \
  unzip

# Setup a custom certificate/SSL settings depending upon build arguments
# Include README.md here so that the build doesn't fail if there is no custom
# certificate specified. Then we just delete it afterwards.
COPY README.md $CUSTOM_CERT /usr/local/share/ca-certificates/
RUN rm /usr/local/share/ca-certificates/README.md \
  && update-ca-certificates
RUN if [ -n "$ENABLE_LEGACY_RENEGOTIATION" ]; then echo "Options = UnsafeLegacyRenegotiation" >> /etc/ssl/openssl.cnf ; fi

# Can this be converted into a native Ubuntu install as in the LLVM case
ENV CARGO_HOME="/cargo"
ENV RUSTUP_HOME="/rustup"
RUN curl https://sh.rustup.rs | sh -s -- -y --default-toolchain none
ENV PATH="$PATH:/cargo/bin"

# LLVM Installation
RUN apt-get -q update \
    && curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key|apt-key add - \
    && apt-add-repository "deb http://apt.llvm.org/`lsb_release -cs`/ llvm-toolchain-`lsb_release -cs`-$LLVM_VERSION main" || true \
    && apt-get -q update \
    && apt-get install -y clang-$LLVM_VERSION llvm-$LLVM_VERSION llvm-$LLVM_VERSION-dev libomp-$LLVM_VERSION-dev \
    && ln -s /usr/bin/clang-$LLVM_VERSION /usr/bin/clang \
    && ln -s /usr/bin/clang++-$LLVM_VERSION /usr/bin/clang++ \
    && ln -s /usr/bin/llvm-objcopy-$LLVM_VERSION /usr/bin/llvm-objcopy \
    && ln -s /usr/bin/opt-$LLVM_VERSION /usr/bin/opt \
    && ln -s /usr/bin/llvm-link-$LLVM_VERSION /usr/bin/llvm-link \
    && ln -s /usr/bin/llvm-ar-$LLVM_VERSION /usr/bin/llvm-ar \
    && ln -s /usr/bin/llvm-nm-$LLVM_VERSION /usr/bin/llvm-nm \
    && ln -s /usr/bin/llvm-extract-$LLVM_VERSION /usr/bin/llvm-extract \
    && ln -s /usr/bin/llvm-bcanalyzer-$LLVM_VERSION /usr/bin/llvm-bcanalyzer

# Install Julia
RUN curl \
    https://julialang-s3.julialang.org/bin/linux/x64/1.$JULIA_MAJOR_VERSION/julia-1.$JULIA_MAJOR_VERSION.$JULIA_MINOR_VERSION-linux-x86_64.tar.gz \
    | tar -xz
RUN mv julia-1.$JULIA_MAJOR_VERSION.$JULIA_MINOR_VERSION/ /opt/
ENV PATH="/opt/julia-1.$JULIA_MAJOR_VERSION.$JULIA_MINOR_VERSION/bin/:${PATH}"

# Install Swift
RUN curl \
    https://download.swift.org/swift-5.8.1-release/ubuntu2204/swift-5.8.1-RELEASE/swift-5.8.1-RELEASE-ubuntu22.04.tar.gz \
    | tar -xz
RUN mv swift-5.$SWIFT_MAJOR_VERSION.$SWIFT_MINOR_VERSION-RELEASE-ubuntu22.04/usr/ /opt/swift-5.$SWIFT_MAJOR_VERSION.$SWIFT_MINOR_VERSION/
ENV PATH="${PATH}:/opt/swift-5.$SWIFT_MAJOR_VERSION.$SWIFT_MINOR_VERSION/bin/"

# Set up the Python dependencies
COPY Pipfile* ./
RUN pip3 install pipenv \
 && pipenv sync --categories "packages dev-packages" --system \
 && pipenv --clear \
 && rm Pipfile*

# Install llvm-tokenizer
WORKDIR /
COPY llvm-tokenizer.tar.gz /
RUN tar -xzf ./llvm-tokenizer.tar.gz \
    && mkdir /llvm-tokenizer/build \
    && cd /llvm-tokenizer/build \
    && cmake -GNinja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr ../ \
    && ninja install

# Clean up the Docker container to make the image smaller
RUN apt-get autoremove -y --purge \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

ENV DEBIAN_FRONTEND=

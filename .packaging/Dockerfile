ARG UBUNTU_VERSION=22.04
ARG JULIA_MAJOR_VERSION=8
ARG JULIA_MINOR_VERSION=3
ARG SWIFT_MAJOR_VERSION=8
ARG SWIFT_MINOR_VERSION=1
ARG CUSTOM_CERT
ARG ENABLE_LEGACY_RENEGOTIATION

FROM ubuntu:$UBUNTU_VERSION

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
RUN git clone -b running-fixes --depth=1 https://github.com/llvm-ml/llvm-project \
    && mkdir /llvm-project/build \
    && cd /llvm-project/build \
    && cmake -GNinja -DCMAKE_BUILD_TYPE=Relase \
         -DLLVM_ENABLE_PROJECTS="clang" \
         -DLLVM_ENABLE_RUNTIMES="compiler-rt;openmp" \
         -DCMAKE_INSTALL_PREFIX=/usr \
         -DLLVM_TARGETS_TO_BUILD=Native \
         ../llvm \
    && ninja install \
    && cd / \
    && rm -rf /llvm-project

# Install Julia
RUN git clone -b emit-per-package-bitcode --depth=1 https://github.com/llvm-ml/julia /julia \
    && cd /julia \
    && make MARCH=x86-64 -j $(nproc) \
    && echo prefix=/usr > Make.user \
    && make MARCH=x86-64 install \
    && cd / \
    && rm -rf /julia

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

# Clean up the Docker container to make the image smaller
RUN apt-get autoremove -y --purge \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

ENV DEBIAN_FRONTEND=

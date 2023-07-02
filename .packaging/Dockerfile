ARG UBUNTU_VERSION=22.04
ARG LLVM_VERSION=16
ARG JULIA_MAJOR_VERSION=8
ARG JULIA_MINOR_VERSION=3
ARG CUSTOM_CERT
ARG ENABLE_LEGACY_RENEGOTIATION

FROM ubuntu:$UBUNTU_VERSION

ARG LLVM_VERSION
ARG JULIA_MAJOR_VERSION
ARG JULIA_MINOR_VERSION
ARG CUSTOM_CERT
ARG ENABLE_LEGACY_RENEGOTIATION

ENV DEBIAN_FRONTEND=noninteractive

# Install the base dependencies
RUN apt-get update && apt-get install -y --no-install-recommends python3 python-is-python3 wget curl lsb-release ca-certificates software-properties-common build-essential gnupg2 python3-pip git pkg-config libssl-dev gcc gfortran

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
RUN rustup toolchain install nightly-2023-06-22 \
    && rustup component add rust-src rustc-dev llvm-tools-preview

# LLVM Installation
RUN apt-get -q update \
    && curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key|apt-key add - \
    && apt-add-repository "deb http://apt.llvm.org/`lsb_release -cs`/ llvm-toolchain-`lsb_release -cs`-$LLVM_VERSION main" || true \
    && apt-get -q update \
    && apt-get install -y clang-$LLVM_VERSION llvm-$LLVM_VERSION llvm-$LLVM_VERSION-dev \
    && ln -s /usr/bin/clang-$LLVM_VERSION /usr/bin/clang \
    && ln -s /usr/bin/clang++-$LLVM_VERSION /usr/bin/clang++ \
    && ln -s /usr/bin/llvm-objcopy-$LLVM_VERSION /usr/bin/llvm-objcopy

# Install and configure Spack
ENV SPACK_ROOT=/opt/spack
ENV PATH=${PATH}:${SPACK_ROOT}/bin
RUN git clone https://github.com/spack/spack.git ${SPACK_ROOT} \
    && git --git-dir=${SPACK_ROOT}/.git --work-tree=${SPACK_ROOT} checkout develop \
    && . ${SPACK_ROOT}/share/spack/setup-env.sh

# Add Spack build cache (AWS)
ENV FORCE_UNSAFE_CONFIGURE=1
RUN spack mirror add binary_mirror https://binaries.spack.io/develop
RUN spack buildcache keys --install --trust

# Install Julia
RUN curl \
    https://julialang-s3.julialang.org/bin/linux/x64/1.$JULIA_MAJOR_VERSION/julia-1.$JULIA_MAJOR_VERSION.$JULIA_MINOR_VERSION-linux-x86_64.tar.gz \
    | tar -xz
RUN mv julia-1.$JULIA_MAJOR_VERSION.$JULIA_MINOR_VERSION/ /opt/
ENV PATH="/opt/julia-1.$JULIA_MAJOR_VERSION.$JULIA_MINOR_VERSION/bin/:${PATH}"

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

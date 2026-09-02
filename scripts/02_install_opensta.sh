#!/usr/bin/env bash
# Build and install OpenSTA (with CUDD BDD library) from source.
# Installs to tools/opensta and creates symlink /usr/local/bin/sta.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/jobs.sh
source "${ROOT}/scripts/lib/jobs.sh"
SRC="${ROOT}/tools/src"
CUDD_PREFIX="${ROOT}/tools/cudd"
STA_PREFIX="${ROOT}/tools/opensta"
JOBS="${EDA_JOBS}"

echo "==> Installing build dependencies..."
sudo apt-get install -y -qq build-essential cmake tcl8.6-dev swig bison flex \
  libeigen3-dev zlib1g-dev libreadline-dev tcl-tclreadline automake autotools-dev \
  libtool libtool-bin m4

mkdir -p "${SRC}"

if [[ ! -d "${SRC}/cudd" ]]; then
  echo "==> Cloning CUDD..."
  git clone --depth 1 https://github.com/The-OpenROAD-Project/cudd.git "${SRC}/cudd"
fi
echo "==> Building CUDD..."
(
  cd "${SRC}/cudd"
  # A fresh clone has timestamps that push autotools targets to regenerate
  # with a pinned aclocal version (aclocal-1.14) not present here.
  # Regenerate autotools files with the local toolchain for robustness.
  autoreconf -fi
  ./configure --prefix="${CUDD_PREFIX}"
  make -j"${JOBS}"
  make install
)

if [[ ! -d "${SRC}/OpenSTA" ]]; then
  echo "==> Cloning OpenSTA..."
  git clone --depth 1 https://github.com/parallaxsw/OpenSTA.git "${SRC}/OpenSTA"
fi
echo "==> Building OpenSTA..."
(
  cd "${SRC}/OpenSTA"
  cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_COMPILER=g++ \
    -DCUDD_DIR="${CUDD_PREFIX}" \
    -DTCL_HEADER=/usr/include/tcl8.6/tcl.h \
    -DCMAKE_INSTALL_PREFIX="${STA_PREFIX}"
  make -C build -j"${JOBS}"
  make -C build install
)

sudo ln -sf "${STA_PREFIX}/bin/sta" /usr/local/bin/sta
echo "==> Installed: OpenSTA $(sta -version)"

#!/usr/bin/env bash
# Clone OpenROAD-flow-scripts (ORFS) and build yosys from the pinned submodule.
# OpenROAD comes from the precompiled package (script 01), so here we
# build only yosys, using CMake or Makefile depending on the revision.
# Installs to tools/yosys and creates /usr/local/bin/yosys.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/jobs.sh
source "${ROOT}/scripts/lib/jobs.sh"
ORFS="${ROOT}/tools/OpenROAD-flow-scripts"
YOSYS_PREFIX="${ROOT}/tools/yosys"
JOBS="${EDA_JOBS}"
ORFS_TAG="${ORFS_TAG:-26Q2}"
if [[ "${ORFS_TAG}" == "26Q2" ]]; then
  ORFS_COMMIT="${ORFS_COMMIT:-036d106273e66855cd5214d49518fd0f0df7de61}"
else
  ORFS_COMMIT="${ORFS_COMMIT:-}"
fi

echo "==> Installing yosys build dependencies..."
sudo apt-get install -y -qq build-essential cmake bison flex time libreadline-dev \
  libffi-dev pkg-config python3-dev zlib1g-dev tcl-dev

if [[ ! -d "${ORFS}" ]]; then
  echo "==> Cloning OpenROAD-flow-scripts ${ORFS_TAG}..."
  git clone --depth 1 --branch "${ORFS_TAG}" \
    https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git "${ORFS}"
else
  echo "==> Aligning OpenROAD-flow-scripts to tag ${ORFS_TAG}..."
  (
    cd "${ORFS}"
    git fetch --depth 1 --force origin "refs/tags/${ORFS_TAG}:refs/tags/${ORFS_TAG}"
    git checkout --detach "${ORFS_TAG}"
  )
fi

if [[ -n "${ORFS_COMMIT}" ]]; then
  (
    cd "${ORFS}"
    if ! git cat-file -e "${ORFS_COMMIT}^{commit}" 2>/dev/null; then
      git fetch --depth 1 origin "${ORFS_COMMIT}"
    fi
    git checkout --detach "${ORFS_COMMIT}"
    [[ "$(git rev-parse HEAD)" == "${ORFS_COMMIT}" ]] || {
      echo "ERROR: ORFS commit verification failed" >&2
      exit 1
    }
  )
fi

echo "==> Initializing yosys submodule..."
(
  cd "${ORFS}"
  git submodule update --init --depth 1 --recursive tools/yosys
)

echo "==> Building yosys..."
(
  cd "${ORFS}/tools/yosys"
  if [[ -f CMakeLists.txt ]]; then
    cmake -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=gcc \
      -DCMAKE_CXX_COMPILER=g++ \
      -DCMAKE_INSTALL_PREFIX="${YOSYS_PREFIX}"
    cmake --build build --target install -j"${JOBS}"
  else
    make config-gcc
    make install -j"${JOBS}" PREFIX="${YOSYS_PREFIX}"
  fi
)

sudo ln -sf "${YOSYS_PREFIX}/bin/yosys" /usr/local/bin/yosys
sudo ln -sf "${YOSYS_PREFIX}/bin/yosys-abc" /usr/local/bin/yosys-abc
echo "==> Installed: $(yosys -V)"

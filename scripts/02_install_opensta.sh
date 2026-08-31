#!/usr/bin/env bash
# Compila e installa OpenSTA (con la libreria BDD CUDD) dai sorgenti.
# Installa in tools/opensta e crea il symlink /usr/local/bin/sta.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${ROOT}/tools/src"
CUDD_PREFIX="${ROOT}/tools/cudd"
STA_PREFIX="${ROOT}/tools/opensta"
JOBS="$(nproc)"

echo "==> Installo le dipendenze di build..."
sudo apt-get install -y -qq build-essential cmake tcl8.6-dev swig bison flex \
  libeigen3-dev zlib1g-dev libreadline-dev tcl-tclreadline automake autotools-dev \
  libtool libtool-bin m4

mkdir -p "${SRC}"

if [[ ! -d "${SRC}/cudd" ]]; then
  echo "==> Clono CUDD..."
  git clone --depth 1 https://github.com/The-OpenROAD-Project/cudd.git "${SRC}/cudd"
fi
echo "==> Compilo CUDD..."
(
  cd "${SRC}/cudd"
  # Il clone fresco ha timestamp che spingono i target autotools a rigenerarsi
  # con una versione pinnata di aclocal (aclocal-1.14) non presente qui.
  # Rigeneriamo i file autotools con la toolchain locale per renderlo robusto.
  autoreconf -fi
  ./configure --prefix="${CUDD_PREFIX}"
  make -j"${JOBS}"
  make install
)

if [[ ! -d "${SRC}/OpenSTA" ]]; then
  echo "==> Clono OpenSTA..."
  git clone --depth 1 https://github.com/parallaxsw/OpenSTA.git "${SRC}/OpenSTA"
fi
echo "==> Compilo OpenSTA..."
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
echo "==> Installato: OpenSTA $(sta -version)"

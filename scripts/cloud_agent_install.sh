#!/usr/bin/env bash
# Cloud Agent bootstrap: prepara l'ambiente completo di physical design.
#
# Idempotente: puo' essere rieseguito senza effetti collaterali. Orchestra
#   1. pacchetti di sistema (build deps + tool ausiliari: iverilog, ngspice, ...)
#   2. toolchain EDA  (OpenROAD, OpenSTA, KLayout, ORFS+yosys)  -> scripts/01..04
#   3. solver nativo  (engine/libdpn.so + dpn_test)
#   4. Studio (Next.js) dependencies
#
# Variabili utili:
#   SKIP_EDA=1     salta l'installazione della toolchain EDA (01..04)
#   SKIP_STUDIO=1  salta npm install in studio/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------------------
# 1. Pacchetti di sistema
# ---------------------------------------------------------------------------
log "Pacchetti di sistema (build deps + tool ausiliari)"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq \
  build-essential cmake g++-13 git curl ca-certificates pkg-config \
  libeigen3-dev libomp-dev \
  tcl8.6-dev swig bison flex libreadline-dev tcl-tclreadline \
  automake autotools-dev libtool libtool-bin m4 \
  zlib1g-dev libffi-dev python3-dev tcl-dev \
  python3-numpy python3-scipy \
  iverilog ngspice \
  xvfb

# ---------------------------------------------------------------------------
# 2. Toolchain EDA (OpenROAD / OpenSTA / KLayout / ORFS + yosys)
# ---------------------------------------------------------------------------
if [[ "${SKIP_EDA:-0}" != "1" ]]; then
  if ! command -v openroad >/dev/null 2>&1; then
    log "OpenROAD (binari Precision Innovations)"
    ./scripts/01_install_openroad.sh
  else
    log "OpenROAD gia' presente: $(openroad -version | head -1)"
  fi

  # Nota: il .deb di OpenROAD fornisce gia' /usr/bin/sta, ma la build
  # standalone porta con se' i sorgenti/examples usati da
  # scripts/run_opensta_example.sh (smoke test documentato nel README).
  if [[ ! -x "${ROOT}/tools/opensta/bin/sta" ]]; then
    log "OpenSTA standalone (build dai sorgenti + CUDD)"
    ./scripts/02_install_opensta.sh
  else
    log "OpenSTA standalone gia' presente: $("${ROOT}/tools/opensta/bin/sta" -version 2>/dev/null | head -1)"
  fi

  if ! command -v klayout >/dev/null 2>&1; then
    log "KLayout (.deb ufficiale)"
    ./scripts/03_install_klayout.sh
  else
    log "KLayout gia' presente: $(klayout -v 2>&1 | head -1)"
  fi

  if ! command -v yosys >/dev/null 2>&1 || [[ ! -d "${ROOT}/tools/OpenROAD-flow-scripts" ]]; then
    log "ORFS + yosys (clone + build dai sorgenti)"
    ./scripts/04_setup_orfs.sh
  else
    log "yosys/ORFS gia' presenti: $(yosys -V 2>/dev/null | head -1)"
  fi
else
  log "SKIP_EDA=1: salto la toolchain EDA"
fi

# ---------------------------------------------------------------------------
# 3. Solver nativo (engine/libdpn.so + dpn_test)
# ---------------------------------------------------------------------------
log "Solver nativo DPN (engine)"
./learn/scripts/build_dpn_engine.sh

# ---------------------------------------------------------------------------
# 4. Studio (Next.js)
# ---------------------------------------------------------------------------
if [[ "${SKIP_STUDIO:-0}" != "1" ]]; then
  log "Studio: dipendenze npm"
  (
    cd studio
    if [[ -f package-lock.json ]]; then
      npm ci
    else
      npm install
    fi
  )
else
  log "SKIP_STUDIO=1: salto npm install"
fi

log "Setup completato."

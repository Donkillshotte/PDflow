#!/usr/bin/env bash
# Cloud Agent bootstrap. Default profile is *core*: enough for Studio + GCD
# RTL→GDS. Does not compile OpenSTA standalone, does not build libdpn, and
# does not run ORFS / DSE / AES / Krylov. Those paths have OOM'd a Cloud VM.
#
# Profiles (PD_FLOW_PROFILE):
#   core      OpenROAD + KLayout + ORFS/yosys + Studio   (default, Cloud Agent)
#   analysis  core + native DPN engine (synthetic dpn_test only)
#   full      analysis + OpenSTA standalone (CUDD) for scripts/run_opensta_example.sh
#
# Variabili:
#   EDA_JOBS=2           parallelismo compilazione (default 2, max 8)
#   SKIP_EDA=1           salta 01..04
#   SKIP_STUDIO=1        salta npm ci
#   PD_FLOW_PROFILE=...  vedi sopra
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
# shellcheck source=lib/jobs.sh
source "${ROOT}/scripts/lib/jobs.sh"

PROFILE="${PD_FLOW_PROFILE:-core}"
case "${PROFILE}" in
  core|analysis|full) ;;
  *)
    echo "ERRORE: PD_FLOW_PROFILE=${PROFILE} (attesi: core|analysis|full)" >&2
    exit 1
    ;;
esac

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

log "Profilo ${PROFILE}  EDA_JOBS=${EDA_JOBS}"
log "Nessun flow OpenROAD / AES / DSE / Krylov in questo script."

# ---------------------------------------------------------------------------
# 1. Pacchetti di sistema
# ---------------------------------------------------------------------------
log "Pacchetti di sistema (build deps + tool ausiliari)"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
APT_PKGS=(
  build-essential cmake g++-13 git curl ca-certificates pkg-config
  tcl8.6-dev swig bison flex libreadline-dev tcl-tclreadline
  automake autotools-dev libtool libtool-bin m4
  zlib1g-dev libffi-dev python3-dev tcl-dev
  python3-numpy python3-scipy
  iverilog ngspice
  xvfb
)
if [[ "${PROFILE}" == "analysis" || "${PROFILE}" == "full" ]]; then
  APT_PKGS+=(libeigen3-dev libomp-dev)
fi
sudo apt-get install -y -qq "${APT_PKGS[@]}"

# ---------------------------------------------------------------------------
# 2. Toolchain EDA (OpenROAD / KLayout / ORFS + yosys)
# ---------------------------------------------------------------------------
if [[ "${SKIP_EDA:-0}" != "1" ]]; then
  if ! command -v openroad >/dev/null 2>&1; then
    log "OpenROAD (binari Precision Innovations)"
    ./scripts/01_install_openroad.sh
  else
    log "OpenROAD gia' presente: $(openroad -version | head -1)"
  fi

  if ! command -v klayout >/dev/null 2>&1; then
    log "KLayout (.deb ufficiale)"
    ./scripts/03_install_klayout.sh
  else
    log "KLayout gia' presente: $(klayout -v 2>&1 | head -1)"
  fi

  if ! command -v yosys >/dev/null 2>&1 || [[ ! -d "${ROOT}/tools/OpenROAD-flow-scripts" ]]; then
    log "ORFS + yosys (clone + build dai sorgenti, EDA_JOBS=${EDA_JOBS})"
    ./scripts/04_setup_orfs.sh
  else
    log "yosys/ORFS gia' presenti: $(yosys -V 2>/dev/null | head -1)"
  fi

  if [[ "${PROFILE}" == "full" ]]; then
    if [[ ! -x "${ROOT}/tools/opensta/bin/sta" ]]; then
      log "OpenSTA standalone (profilo full, EDA_JOBS=${EDA_JOBS})"
      ./scripts/02_install_opensta.sh
    else
      log "OpenSTA standalone gia' presente: $("${ROOT}/tools/opensta/bin/sta" -version 2>/dev/null | head -1)"
    fi
  else
    log "Salto OpenSTA standalone (profilo ${PROFILE}; OpenROAD include STA)"
  fi
else
  log "SKIP_EDA=1: salto la toolchain EDA"
fi

# ---------------------------------------------------------------------------
# 3. Solver nativo — solo analysis/full, e solo dpn_test sintetico
# ---------------------------------------------------------------------------
if [[ "${PROFILE}" == "analysis" || "${PROFILE}" == "full" ]]; then
  log "Solver nativo DPN (engine) — dpn_test sintetico, nessuna mesh reale"
  ./learn/scripts/build_dpn_engine.sh
else
  log "Salto engine/libdpn (profilo core)"
fi

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

# ---------------------------------------------------------------------------
# 5. Smoke versioni — mai un make ORFS
# ---------------------------------------------------------------------------
log "Smoke versioni"
./scripts/cloud_agent_smoke.sh

log "Setup completato (profilo ${PROFILE})."

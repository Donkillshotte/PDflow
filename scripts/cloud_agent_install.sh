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
# Variables:
#   EDA_JOBS=2           build parallelism (default 2, max 8)
#   SKIP_EDA=1           skip 01..04
#   SKIP_STUDIO=1        skip npm ci
#   PD_FLOW_PROFILE=...  see above
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
# shellcheck source=lib/jobs.sh
source "${ROOT}/scripts/lib/jobs.sh"

PROFILE="${PD_FLOW_PROFILE:-core}"
case "${PROFILE}" in
  core|analysis|full) ;;
  *)
    echo "ERROR: PD_FLOW_PROFILE=${PROFILE} (expected: core|analysis|full)" >&2
    exit 1
    ;;
esac

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

log "Profile ${PROFILE}  EDA_JOBS=${EDA_JOBS}"
log "No OpenROAD flow / AES / DSE / Krylov in this script."

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
log "System packages (build deps + auxiliary tools)"
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
# 2. EDA toolchain (OpenROAD / KLayout / ORFS + yosys)
# ---------------------------------------------------------------------------
if [[ "${SKIP_EDA:-0}" != "1" ]]; then
  if ! command -v openroad >/dev/null 2>&1; then
    log "OpenROAD (Precision Innovations binaries)"
    ./scripts/01_install_openroad.sh
  else
    log "OpenROAD already present: $(openroad -version | head -1)"
  fi

  if ! command -v klayout >/dev/null 2>&1; then
    log "KLayout (official .deb)"
    ./scripts/03_install_klayout.sh
  else
    log "KLayout already present: $(klayout -v 2>&1 | head -1)"
  fi

  if ! command -v yosys >/dev/null 2>&1 || [[ ! -d "${ROOT}/tools/OpenROAD-flow-scripts" ]]; then
    log "ORFS + yosys (clone + build from source, EDA_JOBS=${EDA_JOBS})"
    ./scripts/04_setup_orfs.sh
  else
    log "yosys/ORFS already present: $(yosys -V 2>/dev/null | head -1)"
  fi

  if [[ "${PROFILE}" == "full" ]]; then
    if [[ ! -x "${ROOT}/tools/opensta/bin/sta" ]]; then
      log "OpenSTA standalone (full profile, EDA_JOBS=${EDA_JOBS})"
      ./scripts/02_install_opensta.sh
    else
      log "OpenSTA standalone already present: $("${ROOT}/tools/opensta/bin/sta" -version 2>/dev/null | head -1)"
    fi
  else
    log "Skipping OpenSTA standalone (profile ${PROFILE}; OpenROAD includes STA)"
  fi
else
  log "SKIP_EDA=1: skipping EDA toolchain"
fi

# ---------------------------------------------------------------------------
# 3. Native solver — analysis/full only, synthetic dpn_test only
# ---------------------------------------------------------------------------
if [[ "${PROFILE}" == "analysis" || "${PROFILE}" == "full" ]]; then
  log "Native DPN solver (engine) — synthetic dpn_test, no real mesh"
  ./learn/scripts/build_dpn_engine.sh
else
  log "Skipping engine/libdpn (core profile)"
fi

# ---------------------------------------------------------------------------
# 4. Studio (Next.js)
# ---------------------------------------------------------------------------
if [[ "${SKIP_STUDIO:-0}" != "1" ]]; then
  log "Studio: npm dependencies"
  (
    cd studio
    if [[ -f package-lock.json ]]; then
      npm ci
    else
      npm install
    fi
  )
else
  log "SKIP_STUDIO=1: skipping npm install"
fi

# ---------------------------------------------------------------------------
# 5. Version smoke — never an ORFS make
# ---------------------------------------------------------------------------
log "Version smoke"
./scripts/cloud_agent_smoke.sh

log "Setup complete (profile ${PROFILE})."

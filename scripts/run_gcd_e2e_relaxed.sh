#!/usr/bin/env bash
# GCD E2E with the *relaxed* 2.0 ns SDC. Isolated FLOW_VARIANT=e2e_relaxed.
# Does not use AES, DSE, Krylov, or the aggressive 0.46 ns teacher.
#
#   ./scripts/run_gcd_e2e_relaxed.sh synth    # T1
#   ./scripts/run_gcd_e2e_relaxed.sh finish   # T2 RTL→GDS
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
TARGET="${1:-synth}"
VARIANT="${FLOW_VARIANT:-e2e_relaxed}"
TUTORIAL_SRC="${ROOT}/learn/designs/nangate45/gcd-tutorial"
TUTORIAL_ORFS="${FLOW}/designs/nangate45/gcd-tutorial"

if [[ ! -d "${FLOW}" ]]; then
  echo "FAIL missing ORFS in ${FLOW} — run prima lo setup core" >&2
  exit 1
fi

mkdir -p "$(dirname "${TUTORIAL_ORFS}")"
ln -sfn "${TUTORIAL_SRC}" "${TUTORIAL_ORFS}"

SDC="${TUTORIAL_SRC}/constraint_relaxed.sdc"
[[ -f "${SDC}" ]] || { echo "FAIL missing ${SDC}" >&2; exit 1; }

echo "== GCD E2E relaxed  target=${TARGET}  variant=${VARIANT}  sdc=2.0ns =="
cd "${FLOW}"
make \
  DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
  FLOW_VARIANT="${VARIANT}" \
  CORE_UTILIZATION="${CORE_UTILIZATION:-35}" \
  SDC_FILE="${SDC}" \
  OPENROAD_EXE="${OPENROAD_EXE:-$(command -v openroad)}" \
  OPENSTA_EXE="${OPENSTA_EXE:-$(command -v sta)}" \
  YOSYS_EXE="${YOSYS_EXE:-$(command -v yosys)}" \
  "${TARGET}"

RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
case "${TARGET}" in
  synth)
    [[ -f "${RES}/1_synth.odb" ]] || { echo "FAIL missing 1_synth.odb" >&2; exit 1; }
    echo "OK synth ${RES}/1_synth.odb"
    ;;
  finish)
    [[ -f "${RES}/6_final.odb" ]] || { echo "FAIL missing 6_final.odb" >&2; exit 1; }
    [[ -f "${RES}/6_final.gds" ]] || { echo "FAIL missing 6_final.gds" >&2; exit 1; }
    echo "OK finish ${RES}/6_final.gds"
    ;;
esac

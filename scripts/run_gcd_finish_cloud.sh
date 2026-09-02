#!/usr/bin/env bash
# GCD FlowLab RTL→GDS (0.46 ns teacher) with an 8 GiB cap.
# Restores 6_final.odb so Dynamic IR gold can run. Does not run AES or Krylov.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
VARIANT="${FLOW_VARIANT:-flowlab}"
if [[ "${VARIANT}" == *aes* ]] || [[ "${DESIGN_ID:-}" == *aes* ]]; then
  echo "REFUSED: this wrapper is GCD FlowLab finish only." >&2
  exit 2
fi
TUTORIAL_SRC="${ROOT}/learn/designs/nangate45/gcd-tutorial"
TUTORIAL_ORFS="${FLOW}/designs/nangate45/gcd-tutorial"
mkdir -p "$(dirname "${TUTORIAL_ORFS}")"
ln -sfn "${TUTORIAL_SRC}" "${TUTORIAL_ORFS}"
SDC="${TUTORIAL_SRC}/constraint.sdc"
[[ -f "${SDC}" ]] || { echo "FAIL missing ${SDC}" >&2; exit 1; }
AS_BYTES="${PDN_AS_BYTES:-8589934592}"
CPU_S="${PDN_CPU_S:-900}"
echo "GCD finish cloud: variant=${VARIANT} sdc=0.46ns as=${AS_BYTES} cpu=${CPU_S}s"
cd "${FLOW}"
exec prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
  make \
    DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
    FLOW_VARIANT="${VARIANT}" \
    CORE_UTILIZATION="${CORE_UTILIZATION:-35}" \
    SDC_FILE="${SDC}" \
    OPENROAD_EXE="${OPENROAD_EXE:-$(command -v openroad)}" \
    OPENSTA_EXE="${OPENSTA_EXE:-$(command -v sta)}" \
    YOSYS_EXE="${YOSYS_EXE:-$(command -v yosys)}" \
    finish

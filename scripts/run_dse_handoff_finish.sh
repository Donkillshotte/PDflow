#!/usr/bin/env bash
# Cook one DSE winner through ORFS make finish in an isolated FLOW_VARIANT.
# Never overwrites gcd/flowlab. Never AES/Krylov. Yosys mapping is skipped
# via SYNTH_NETLIST_FILES (gate-level DSE .v is copied to 1_2_yosys.v).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
VARIANT="${FLOW_VARIANT:-}"
NETLIST="${SYNTH_NETLIST_FILES:-}"
TARGET="${1:-finish}"

if [[ -z "${VARIANT}" ]]; then
  echo "REFUSED: set FLOW_VARIANT (e.g. flowlab_dse_small). flowlab is locked." >&2
  exit 2
fi
if [[ "${VARIANT}" == "flowlab" || "${VARIANT}" == "learn" ]]; then
  echo "REFUSED: FLOW_VARIANT=${VARIANT} would collide with baseline/course runs." >&2
  exit 2
fi
if [[ "${VARIANT}" == *aes* ]] || [[ "${DESIGN_ID:-}" == *aes* ]]; then
  echo "REFUSED: GCD handoff only — no AES." >&2
  exit 2
fi
if [[ -z "${NETLIST}" || ! -f "${NETLIST}" ]]; then
  echo "REFUSED: SYNTH_NETLIST_FILES must be an existing DSE gate netlist." >&2
  exit 2
fi
if ! grep -qE '^module gcd\(' "${NETLIST}"; then
  echo "REFUSED: ${NETLIST} is not module gcd." >&2
  exit 2
fi

TUTORIAL_SRC="${ROOT}/learn/designs/nangate45/gcd-tutorial"
TUTORIAL_ORFS="${FLOW}/designs/nangate45/gcd-tutorial"
mkdir -p "$(dirname "${TUTORIAL_ORFS}")"
ln -sfn "${TUTORIAL_SRC}" "${TUTORIAL_ORFS}"
SDC="${TUTORIAL_SRC}/constraint.sdc"
[[ -f "${SDC}" ]] || { echo "FAIL manca ${SDC}" >&2; exit 1; }

AS_BYTES="${PDN_AS_BYTES:-8589934592}"
CPU_S="${PDN_CPU_S:-900}"
CORE_UTILIZATION="${CORE_UTILIZATION:-35}"

echo "DSE handoff finish: variant=${VARIANT} netlist=${NETLIST} target=${TARGET} util=${CORE_UTILIZATION} sdc=0.46ns as=${AS_BYTES}"
cd "${FLOW}"
exec prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
  make \
    DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
    FLOW_VARIANT="${VARIANT}" \
    CORE_UTILIZATION="${CORE_UTILIZATION}" \
    SDC_FILE="${SDC}" \
    SYNTH_NETLIST_FILES="${NETLIST}" \
    OPENROAD_EXE="${OPENROAD_EXE:-$(command -v openroad)}" \
    OPENSTA_EXE="${OPENSTA_EXE:-$(command -v sta)}" \
    YOSYS_EXE="${YOSYS_EXE:-$(command -v yosys)}" \
    "${TARGET}"

#!/usr/bin/env bash
# Activity → report_power on final ODB.
# Uses gate VCD from gate_sim when present (preferred name-join), else RTL VCD, else synthetic.
#
# Env: FLOW_VARIANT=learn|flowlab (default flowlab — aligned with power_chain)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" activity-power bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
source "${ROOT}/scripts/rg_compat.sh"
# shellcheck source=learn/lib/power_vcd.sh
source "${ROOT}/learn/lib/power_vcd.sh"

VARIANT="${FLOW_VARIANT:-flowlab}"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ODB="${RES}/6_final.odb"
SDC="${PD_FLOW_SDC_FILE:-${ROOT}/learn/designs/nangate45/gcd-tutorial/constraint.sdc}"
[[ -f "${ODB}" ]] || { echo "FAIL missing ${ODB} (variant=${VARIANT})"; exit 1; }

OUT="${ROOT}/learn/sim/reports/activity_power_${VARIANT}.log"
mkdir -p "$(dirname "${OUT}")"

ACTIVITY_TCL="$(power_activity_tcl "${ROOT}")"

cd "${FLOW}"
openroad -no_init -no_splash -exit <<EOF | tee "${OUT}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
${ACTIVITY_TCL}
report_power
puts "ACTIVITY_POWER_DONE ${VARIANT}"
EOF
rg -q 'ACTIVITY_POWER_DONE' "${OUT}"
echo "OK activity power ${VARIANT} → ${OUT}"
if power_vcd_path "${ROOT}" >/dev/null 2>&1; then
  echo "  source: VCD $(power_vcd_path "${ROOT}")"
else
  echo "  source: synthetic (run gate_sim for name-join VCD, or rtl_sim)"
fi

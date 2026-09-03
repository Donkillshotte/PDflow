#!/usr/bin/env bash
# Vectorless + dynamic power/IR comparison on 6_final.odb (GCD Nangate45).
#
# Vectorless IR follows the current-constraint idea of Kouroussis & Najm
# (DAC 2003): instance currents lie in [0, I_max], chip current is bounded,
# worst drop is estimated without a simulation vector. Dynamic mode uses
# Gate VCD on matching names (OpenSTA read_vcd) when gcd_gate.vcd exists.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=learn/lib/power_vcd.sh
source "${ROOT}/learn/lib/power_vcd.sh"

VARIANT="${FLOW_VARIANT:-flowlab}"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ODB="${RES}/6_final.odb"
SDC="${FLOW}/designs/nangate45/gcd-tutorial/constraint.sdc"
OUT_DIR="${ROOT}/learn/sim/reports"
SPICE="${RES}/pdn/pg_vdd_bumps.sp"
INSTS="${RES}/pdn/inst_power_map.json"
mkdir -p "${OUT_DIR}" "${RES}/pdn"

[[ -f "${ODB}" ]] || { echo "FAIL missing ${ODB}"; exit 1; }

openroad -python -no_init -exit \
  "${ROOT}/learn/scripts/export_odb_inst_power.py" "${ODB}" "${INSTS}"

run_mode() {
  local mode="$1"
  local log="${OUT_DIR}/power_${mode}_${VARIANT}.log"
  local tcl
  POWER_MODE="${mode}"
  tcl="$(power_activity_tcl "${ROOT}")"
  cd "${FLOW}"
  openroad -no_init -no_splash -exit <<EOF | tee "${log}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
${tcl}
report_power
analyze_power_grid -net VDD -source_type STRAPS
puts "POWER_MODE_DONE ${mode} ${VARIANT}"
EOF
}

run_mode vectorless
run_mode dynamic

python3 "${ROOT}/learn/scripts/vectorless_analysis.py" \
  --variant "${VARIANT}" \
  --insts "${INSTS}" \
  --vectorless-log "${OUT_DIR}/power_vectorless_${VARIANT}.log" \
  --dynamic-log "${OUT_DIR}/power_dynamic_${VARIANT}.log" \
  --spice "${SPICE}" \
  --out "${OUT_DIR}/vectorless_${VARIANT}.json"

python3 - <<PY
import json, sys
p = "${OUT_DIR}/vectorless_${VARIANT}.json"
j = json.load(open(p))
sys.exit(0 if j.get("ok") else 1)
PY
echo "OK vectorless ${VARIANT} → ${OUT_DIR}/vectorless_${VARIANT}.json"

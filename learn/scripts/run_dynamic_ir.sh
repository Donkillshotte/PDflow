#!/usr/bin/env bash
# Dynamic IR engine on the GCD write_pg_spice mesh.
# Per-ITerm PWL + Solver A (LU golden) + Solver B (SA-AMG) on shared A=G+C/Δt.
# Solver C = same operator, extra I(t) scenarios. vyges-em-ir is bootstrap.
#
# Uso: FLOW_VARIANT=flowlab ./learn/scripts/run_dynamic_ir.sh
# Env:
#   DYNAMIC_IR_MODE=clock|spatial|simultaneous
#   PEAK_FACTOR=8  C_DECAP=50e-15  PKG_R=0.05  PKG_L=2e-10
#   PERIOD_NS=0.46  DUR_NS=0.08  DT_PS=10
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${ROOT}/learn/lib/power_vcd.sh"
export PYTHONPATH="/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"

VARIANT="${FLOW_VARIANT:-flowlab}"
MODE="${DYNAMIC_IR_MODE:-clock}"
PEAK_FACTOR="${PEAK_FACTOR:-8}"
C_DECAP="${C_DECAP:-50e-15}"
PKG_R="${PKG_R:-0.05}"
PKG_L="${PKG_L:-2e-10}"
PERIOD_NS="${PERIOD_NS:-0.46}"
DUR_NS="${DUR_NS:-0.08}"
T50_NS="${T50_NS:-0.12}"
DT_PS="${DT_PS:-10}"

FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ODB="${RES}/6_final.odb"
SDC="${FLOW}/designs/nangate45/gcd-tutorial/constraint.sdc"
SPICE="${RES}/pdn/pg_vdd_bumps.sp"
INSTS="${RES}/pdn/inst_power_map.json"
OUT_DIR="${ROOT}/learn/sim/reports"
JSON="${OUT_DIR}/dynamic_ir_${VARIANT}.json"
LOG="${OUT_DIR}/dynamic_ir_${VARIANT}.log"
STAMP="${RES}/.dynamic_ir.ok"

[[ -f "${ODB}" ]] || { echo "FAIL manca ${ODB} — esegui finish (variant=${VARIANT})"; exit 1; }
mkdir -p "${OUT_DIR}" "${RES}/pdn"
: > "${LOG}"

if [[ ! -f "${INSTS}" ]]; then
  echo "=== export inst_power_map ===" | tee -a "${LOG}"
  openroad -python -no_init -exit \
    "${ROOT}/learn/scripts/export_odb_inst_power.py" "${ODB}" "${INSTS}" \
    2>&1 | tee -a "${LOG}"
fi

if [[ ! -f "${SPICE}" ]]; then
  echo "=== write_pg_spice (mesh assente) ===" | tee -a "${LOG}"
  ACTIVITY_TCL="$(power_activity_tcl "${ROOT}")"
  cd "${FLOW}"
  openroad -no_init -no_splash -exit <<EOF | tee -a "${LOG}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
${ACTIVITY_TCL}
report_power
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 -bump_size 70 -bump_interval 3 -external_resistance ${PKG_R}
analyze_power_grid -net VDD -source_type BUMPS
write_pg_spice -net VDD -source_type BUMPS ${SPICE}
puts "DYNAMIC_IR_SPICE_EXPORT_DONE"
EOF
  rg -q 'DYNAMIC_IR_SPICE_EXPORT_DONE' "${LOG}"
fi
[[ -f "${SPICE}" ]] || { echo "FAIL manca ${SPICE}"; exit 1; }

echo "=== pdn_dynamic.py mode=${MODE} ===" | tee -a "${LOG}"
python3 "${ROOT}/learn/scripts/pdn_dynamic.py" \
  --spice "${SPICE}" \
  --insts "${INSTS}" \
  --out "${JSON}" \
  --mode "${MODE}" \
  --peak-factor "${PEAK_FACTOR}" \
  --period-ns "${PERIOD_NS}" \
  --dur-ns "${DUR_NS}" \
  --t50-ns "${T50_NS}" \
  --pkg-r "${PKG_R}" \
  --pkg-l "${PKG_L}" \
  --c-decap "${C_DECAP}" \
  --dt-ps "${DT_PS}" \
  2>&1 | tee -a "${LOG}"

rg -q 'DYNAMIC_IR_DONE' "${LOG}"
[[ -f "${JSON}" ]] || { echo "FAIL manca ${JSON}"; exit 1; }
date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
echo "OK dynamic IR ${VARIANT} mode=${MODE}"
echo "  report: ${JSON}"
echo "  svg:    ${OUT_DIR}/dynamic_ir_${VARIANT}.svg"

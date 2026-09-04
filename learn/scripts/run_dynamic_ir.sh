#!/usr/bin/env bash
# Dynamic IR engine on the GCD write_pg_spice mesh.
# Per-ITerm PWL + A LU gold + B SA-AMG + C Krylov MOR + D RAS Schwarz.
# Extract = SPICE + tech LEF (EM J); SPEF PG *D_NET *CAP is stamped by name-join
# (GCD OpenRCX has no VDD — GAP; signal nets are never mapped).
# Grover on-die L is estimated always; descriptor TRAN is ON_DIE_L=1 (not AMG).
# Dual-rail VSS: write_pg_spice -net VSS independently of VDD; pair by Sink-for
# inst (not RTL). VSS TRAN does not change VDD gold 45.298 mV.
# Rail-to-rail C is opt-in: instance-pin C_rr (RAIL_C=1) and/or overlapping-strap
# Cox (RAIL_C_GEOM=1) — not the GCD default.
# Electrothermal: default ON reports one-shot R(T) Solver A TRAN (not gold).
#   ELECTROTHERMAL=0 skips that TRAN; N1 restamp still reported.
# Activity = OpenSTA arrival t50 (clock) + VCD/SAIF name-join
# (gate VCD from gate_sim joins; RTL tb_gcd stays GAP).
# SAIF idle-zeros TC=0 pulses; does not invent t50 or rescale I_avg.
# Path STA delay from OpenSTA report_checks (NLDM typical-V × (Vdd/V)^α).
# Ranking of extra I(t) stays Solver A (synthetic). vyges-em-ir is bootstrap.
#
# Usage: FLOW_VARIANT=flowlab ./learn/scripts/run_dynamic_ir.sh
# Env:
#   DYNAMIC_IR_MODE=clock|spatial|simultaneous
#   PEAK_FACTOR=8  C_DECAP=50e-15  PKG_R=0.05  PKG_L=2e-10
#   PERIOD_NS=0.46  DUR_NS=0.08  DT_PS=10
#   DYNAMIC_IR_ADAPTIVE=1  also run adaptive-Δt BE (different L discretization)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${ROOT}/learn/lib/power_vcd.sh"
source "${ROOT}/scripts/lib/heavy_analysis.sh"
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
LEF="${FLOW}/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef"
SPEF="${RES}/6_final.spef"
ODB="${RES}/6_final.odb"
SDC="${FLOW}/designs/nangate45/gcd-tutorial/constraint.sdc"
SPICE="${RES}/pdn/pg_vdd_bumps.sp"
SPICE_VSS="${RES}/pdn/pg_vss_bumps.sp"
INSTS="${RES}/pdn/inst_power_map.json"
OUT_DIR="${ROOT}/learn/sim/reports"
# current_run I(t). Gold 45.298 mV is dynamic_ir_flowlab.json — do not restamp.
JSON="${OUT_DIR}/dynamic_ir_${VARIANT}_direct.json"
LOG="${OUT_DIR}/dynamic_ir_${VARIANT}_direct.log"
STA_JSON="${OUT_DIR}/sta_arrivals_${VARIANT}.json"
VCD=""
if VCD="$(power_vcd_path "${ROOT}")"; then
  :
else
  VCD=""
fi
STAMP="${RES}/.dynamic_ir.ok"

if [[ "$(basename "${JSON}")" == "dynamic_ir_flowlab.json" ]]; then
  echo "FAIL refuse: will not write locked gold Dynamic IR 45.298 mV"
  exit 2
fi

[[ -f "${ODB}" ]] || { echo "FAIL missing ${ODB} — run finish first (variant=${VARIANT})"; exit 1; }
mkdir -p "${OUT_DIR}" "${RES}/pdn"
: > "${LOG}"

if [[ -f "${SPICE}" ]]; then
  n_r="$(grep -cE '^[Rr]' "${SPICE}" || true)"
  n_r="${n_r:-0}"
  if [[ "${n_r}" -gt 20000 ]]; then
    require_heavy_analysis "dynamic IR spice n_r=${n_r} > 20000" | tee -a "${LOG}" || exit 2
  fi
fi

if [[ ! -f "${ROOT}/engine/build/libdpn.so" ]]; then
  echo "=== build libdpn ===" | tee -a "${LOG}"
  "${ROOT}/learn/scripts/build_dpn_engine.sh" 2>&1 | tee -a "${LOG}"
fi

if [[ ! -f "${INSTS}" ]]; then
  echo "=== export inst_power_map ===" | tee -a "${LOG}"
  openroad -python -no_init -exit \
    "${ROOT}/learn/scripts/export_odb_inst_power.py" "${ODB}" "${INSTS}" \
    2>&1 | tee -a "${LOG}"
fi

write_pg_net() {
  local net="$1"
  local out="$2"
  echo "=== write_pg_spice -net ${net} ===" | tee -a "${LOG}"
  local ACTIVITY_TCL
  ACTIVITY_TCL="$(power_activity_tcl "${ROOT}")"
  cd "${FLOW}"
  openroad -no_init -no_splash -exit <<EOF | tee -a "${LOG}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
${ACTIVITY_TCL}
report_power
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 -bump_size 70 -bump_interval 3 -external_resistance ${PKG_R}
analyze_power_grid -net ${net} -source_type BUMPS
write_pg_spice -net ${net} -source_type BUMPS ${out}
puts "DYNAMIC_IR_SPICE_${net}_DONE"
EOF
  rg -q "DYNAMIC_IR_SPICE_${net}_DONE" "${LOG}"
}

if [[ ! -f "${SPICE}" ]]; then
  write_pg_net VDD "${SPICE}"
fi
[[ -f "${SPICE}" ]] || { echo "FAIL missing ${SPICE}"; exit 1; }

if [[ ! -f "${SPICE_VSS}" ]]; then
  write_pg_net VSS "${SPICE_VSS}"
fi

if ! command -v sta >/dev/null 2>&1; then
  echo "FAIL OpenSTA (sta) not in PATH — needed for arrival t50" | tee -a "${LOG}"
  exit 1
fi
echo "=== OpenSTA report_arrival → ${STA_JSON} ===" | tee -a "${LOG}"
unset STA_OUT
STA_LIB="${LIB}" STA_V="${RES}/6_final.v" STA_SDC="${SDC}" FLOW_VARIANT="${VARIANT}" \
  python3 "${ROOT}/learn/scripts/export_sta_arrivals.py" 2>&1 | tee -a "${LOG}"
[[ -f "${STA_JSON}" ]] || { echo "FAIL missing ${STA_JSON}"; exit 1; }
rg -q 'STA_ARRIVALS_JSON' "${LOG}"

echo "=== pdn_dynamic.py mode=${MODE} ===" | tee -a "${LOG}"
ADAPT=()
if [[ "${DYNAMIC_IR_ADAPTIVE:-}" == "1" ]]; then
  ADAPT=(--adaptive)
fi
EXTRA=()
if [[ -f "${LEF}" ]]; then
  EXTRA+=(--lef "${LEF}")
fi
if [[ -f "${SPEF}" ]]; then
  EXTRA+=(--spef "${SPEF}")
fi
EXTRA+=(--sta "${STA_JSON}")
if [[ -n "${VCD}" && -f "${VCD}" ]]; then
  EXTRA+=(--vcd "${VCD}")
fi
if [[ "${ON_DIE_L:-}" == "1" ]]; then
  EXTRA+=(--on-die-l)
fi
if [[ "${RAIL_C:-}" == "1" ]]; then
  EXTRA+=(--rail-c)
  if [[ -n "${RAIL_C_F:-}" ]]; then
    EXTRA+=(--rail-c-f "${RAIL_C_F}")
  fi
fi
if [[ "${RAIL_C_GEOM:-}" == "1" ]]; then
  EXTRA+=(--rail-c-geom)
fi
if [[ "${ELECTROTHERMAL:-1}" == "0" ]]; then
  EXTRA+=(--no-electrothermal)
fi
if [[ -f "${SPICE_VSS}" ]]; then
  EXTRA+=(--spice-vss "${SPICE_VSS}")
fi
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
  --liberty "${LIB}" \
  "${EXTRA[@]}" \
  "${ADAPT[@]}" \
  2>&1 | tee -a "${LOG}"

rg -q 'DYNAMIC_IR_DONE' "${LOG}"
[[ -f "${JSON}" ]] || { echo "FAIL missing ${JSON}"; exit 1; }
date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
echo "OK dynamic IR ${VARIANT} mode=${MODE}"
echo "  report: ${JSON}"
echo "  svg:    ${OUT_DIR}/dynamic_ir_${VARIANT}_direct.svg"

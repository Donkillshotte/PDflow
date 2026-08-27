#!/usr/bin/env bash
# System / package PDN analysis — static (OpenROAD PDNSim) + transient IR.
#
# Stack (open ecosystem):
#   1. OpenROAD psm: set_pdnsim_source_settings + analyze_power_grid
#      + write_pg_spice  (static IR, package R, bump/strap sources)
#   2. learn/scripts/pdn_transient.py — backward-Euler dynamic IR on that
#      SPICE mesh (VoltSpot / vyges-em-ir style), with package R/L + decap
#
# Uso: run_system_pdn.sh
# Env:
#   FLOW_VARIANT=learn|flowlab
#   PKG_R=0.05          # package series resistance (ohm)
#   PKG_L=2e-10         # package series inductance (H)
#   C_DECAP=50e-15      # decap per load node (F)
#   PEAK_FACTOR=8       # simultaneous-switch peak vs average current
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-learn}"
PKG_R="${PKG_R:-0.05}"
PKG_L="${PKG_L:-2e-10}"
C_DECAP="${C_DECAP:-50e-15}"
PEAK_FACTOR="${PEAK_FACTOR:-8}"

FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ODB="${RES}/6_final.odb"
SDC="${FLOW}/designs/nangate45/gcd-tutorial/constraint.sdc"

[[ -f "${ODB}" ]] || { echo "FAIL manca ${ODB} — esegui finish (variant=${VARIANT})"; exit 1; }
[[ -f "${LIB}" ]] || { echo "FAIL manca liberty"; exit 1; }
[[ -f "${SDC}" ]] || { echo "FAIL manca SDC"; exit 1; }

OUT_DIR="${ROOT}/learn/sim/reports"
mkdir -p "${OUT_DIR}" "${RES}/pdn"
LOG="${OUT_DIR}/system_pdn_${VARIANT}.log"
STAMP="${RES}/.system_pdn.ok"
SPICE_BUMPS="${RES}/pdn/pg_vdd_bumps.sp"
VOLT_BUMPS="${RES}/pdn/ir_bumps.csv"
TRANSIENT_JSON="${OUT_DIR}/pdn_transient_${VARIANT}.json"
TRANSIENT_WAVE="${OUT_DIR}/pdn_transient_${VARIANT}.wave.csv"

cd "${FLOW}"
openroad -no_init -no_splash -exit <<EOF | tee "${LOG}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
set_power_activity -global -activity 0.2 -duty 0.5
report_power

# Package-aware static source model (OpenROAD PDNSim)
# bump_* in microns per OpenROAD docs; external_resistance = package R
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 -bump_size 70 -bump_interval 3 -external_resistance ${PKG_R}

puts "=== STATIC STRAPS (board strap proxy) ==="
analyze_power_grid -net VDD -source_type STRAPS
analyze_power_grid -net VSS -source_type STRAPS

puts "=== STATIC FULL ==="
analyze_power_grid -net VDD -source_type FULL
analyze_power_grid -net VSS -source_type FULL

puts "=== STATIC BUMPS (C4-like package bumps) + voltage map ==="
analyze_power_grid -net VDD -source_type BUMPS -voltage_file ${VOLT_BUMPS}
analyze_power_grid -net VSS -source_type BUMPS

puts "=== EXPORT write_pg_spice (BUMPS) for transient engine ==="
write_pg_spice -net VDD -source_type BUMPS ${SPICE_BUMPS}

puts "SYSTEM_PDN_STATIC_DONE ${VARIANT}"
EOF

rg -q 'SYSTEM_PDN_STATIC_DONE' "${LOG}"
rg -q 'Worstcase IR drop' "${LOG}"
[[ -f "${SPICE_BUMPS}" ]] || { echo "FAIL manca spice ${SPICE_BUMPS}"; exit 1; }

echo "=== TRANSIENT IR (pdn_transient.py · VoltSpot/vyges-style) ===" | tee -a "${LOG}"
export PYTHONPATH="/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
python3 "${ROOT}/learn/scripts/pdn_transient.py" \
  --spice "${SPICE_BUMPS}" \
  --out "${TRANSIENT_JSON}" \
  --wave "${TRANSIENT_WAVE}" \
  --mode BUMPS \
  --pkg-r "${PKG_R}" \
  --pkg-l "${PKG_L}" \
  --c-decap "${C_DECAP}" \
  --peak-factor "${PEAK_FACTOR}" \
  2>&1 | tee -a "${LOG}"

rg -q 'PDN_TRANSIENT_DONE' "${LOG}"
[[ -f "${TRANSIENT_JSON}" ]] || { echo "FAIL manca ${TRANSIENT_JSON}"; exit 1; }

python3 - <<PY | tee -a "${LOG}"
import json
r=json.load(open("${TRANSIENT_JSON}"))
print("SUMMARY", r["summary"])
print("STATIC_IR_mV", round(r["static"]["worst_ir"]*1e3, 4))
print("TRANSIENT_DROOP_mV", round(r["transient"]["worst_droop"]*1e3, 4))
print("TRANSIENT_DROOP_PCT", round(r["transient"]["worst_droop_pct"], 4))
PY

date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
echo "SYSTEM_PDN_DONE ${VARIANT}" | tee -a "${LOG}"
echo "OK system PDN+transient ${VARIANT}"
echo "  static log: ${LOG}"
echo "  spice:      ${SPICE_BUMPS}"
echo "  transient:  ${TRANSIENT_JSON}"
echo "  waveform:   ${TRANSIENT_WAVE}"
echo "Nota: OpenROAD PDNSim=static; transient=studio engine su write_pg_spice (non LEF package reale)."

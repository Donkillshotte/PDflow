#!/usr/bin/env bash
# Educational IR-aware STA: OpenSTA worst path × per-cell ITerm V.
# Does not change nominal WNS/TNS. Does not restamp gold Dynamic IR 45.298 mV.
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
OUT_DIR="${ROOT}/learn/sim/reports"
STA="${OUT_DIR}/sta_arrivals_${VARIANT}.json"
OUT="${OUT_DIR}/sta_ir_aware_${VARIANT}.json"
SPICE="${RES}/pdn/pg_vdd_bumps.sp"
[[ -f "${SPICE}" ]] || SPICE="${RES}/pdn/pg_vdd.sp"

# current_run I(t) only. Gold 45.298 mV map is dynamic_ir_flowlab.map.csv.
MAP="${OUT_DIR}/dynamic_ir_${VARIANT}_direct.map.csv"

export PYTHONPATH="${ROOT}/learn/scripts:/usr/lib/python3/dist-packages${PYTHONPATH:+:${PYTHONPATH}}"

[[ -f "${STA}" ]] || { echo "FAIL missing ${STA} — run dynamic_ir or export_sta_arrivals first"; exit 1; }
[[ -f "${SPICE}" ]] || { echo "FAIL missing ${SPICE} — run chip_pdn_ir / write_pg_spice first"; exit 1; }
if [[ "$(basename "${MAP}")" == "dynamic_ir_flowlab.map.csv" ]]; then
  echo "FAIL refuse: will not scale STA from locked gold Dynamic IR map"
  exit 2
fi
[[ -f "${MAP}" ]] || { echo "FAIL missing ${MAP} — run dynamic_ir current_run first"; exit 1; }

mkdir -p "${OUT_DIR}"
python3 "${ROOT}/learn/scripts/sta_ir_aware.py" \
  --sta "${STA}" \
  --spice "${SPICE}" \
  --map "${MAP}" \
  --out "${OUT}" \
  --variant "${VARIANT}"
echo "STA_IR_AWARE_JSON ${OUT}"

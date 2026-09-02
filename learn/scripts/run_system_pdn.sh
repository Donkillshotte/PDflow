#!/usr/bin/env bash
# Hierarchical *System* PDN — VRM → board → package → die (ngspice).
#
# This is NOT chip PDNSim. For on-die IR (OpenROAD + write_pg_spice +
# pdn_transient.py) use: learn/scripts/run_chip_pdn_ir.sh
#
# Usage: run_system_pdn.sh
# Env:
#   FLOW_VARIANT=learn|flowlab
#   SYSTEM_PDN_CONFIG=learn/system_pdn/default.json
#   I_DIE_AVG=0          # 0 = auto from activity_power / reports
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-learn}"
CFG="${SYSTEM_PDN_CONFIG:-${ROOT}/learn/system_pdn/default.json}"
I_DIE_AVG="${I_DIE_AVG:-0}"

FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
OUT_DIR="${ROOT}/learn/sim/reports"
WORK="${RES}/system_pdn"
LOG="${OUT_DIR}/system_pdn_${VARIANT}.log"
REPORT="${OUT_DIR}/system_pdn_${VARIANT}.json"
STAMP="${RES}/.system_pdn.ok"

mkdir -p "${OUT_DIR}" "${WORK}"
: > "${LOG}"

[[ -f "${CFG}" ]] || { echo "FAIL missing config ${CFG}"; exit 1; }

# Prefer finished design if present (for current estimate); not strictly required
if [[ -f "${RES}/6_final.odb" ]]; then
  echo "=== System PDN · finish ODB presente (${VARIANT}) ===" | tee -a "${LOG}"
else
  echo "=== System PDN · ODB missing — uso I_DIE default/config ===" | tee -a "${LOG}"
fi

echo "=== Hierarchical System PDN (ngspice) · VRM→board→pkg→die ===" | tee -a "${LOG}"
EXTRA=()
if [[ "${I_DIE_AVG}" != "0" && -n "${I_DIE_AVG}" ]]; then
  EXTRA+=(--i-die "${I_DIE_AVG}")
fi

python3 "${ROOT}/learn/scripts/system_pdn_hier.py" \
  --config "${CFG}" \
  --out-dir "${WORK}" \
  --report "${REPORT}" \
  --repo "${ROOT}" \
  --variant "${VARIANT}" \
  "${EXTRA[@]}" \
  2>&1 | tee -a "${LOG}"

rg -q 'SYSTEM_PDN_HIER_DONE' "${LOG}"
[[ -f "${REPORT}" ]] || { echo "FAIL missing ${REPORT}"; exit 1; }

python3 - <<PY | tee -a "${LOG}"
import json
r=json.load(open("${REPORT}"))
assert r.get("kind")=="system_pdn", r.get("kind")
assert r.get("engine")=="ngspice-hierarchical"
print("SUMMARY", r["summary"])
print("DIE_DROOP_mV", round(r["transient"]["droop_mv"], 4))
print("ZMAX_mOhm", round(r["impedance"]["z_max_mohm"], 4))
print("F_ZMAX_Hz", r["impedance"]["f_at_zmax_hz"])
print("DOMAINS", ",".join(r["domains"]))
PY

date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
echo "SYSTEM_PDN_DONE ${VARIANT}" | tee -a "${LOG}"
echo "OK System PDN hierarchical ${VARIANT}"
echo "  log:    ${LOG}"
echo "  report: ${REPORT}"
echo "  work:   ${WORK}"
echo "Note: chip on-die IR → ./learn/scripts/run_chip_pdn_ir.sh"

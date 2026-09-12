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
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" system-pdn bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
source "${ROOT}/scripts/rg_compat.sh"
VARIANT="${FLOW_VARIANT:-learn}"
CFG="${SYSTEM_PDN_CONFIG:-${ROOT}/learn/system_pdn/default.json}"
I_DIE_AVG="${I_DIE_AVG:-0}"

FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
OUT_DIR="${PD_FLOW_SYSTEM_PDN_OUTPUT_DIR:-${ROOT}/learn/sim/reports}"
WORK="${PD_FLOW_SYSTEM_PDN_WORK_DIR:-${RES}/system_pdn}"
LOG="${PD_FLOW_SYSTEM_PDN_LOG:-${OUT_DIR}/system_pdn_${VARIANT}.log}"
REPORT="${PD_FLOW_SYSTEM_PDN_REPORT:-${OUT_DIR}/system_pdn_${VARIANT}.json}"
STAMP="${PD_FLOW_SYSTEM_PDN_STAMP:-${RES}/.system_pdn.ok}"
HIER_RUN_DIR="${PD_FLOW_SYSTEM_PDN_RUN_DIR:-}"
HIER_RUN_ID="${PD_FLOW_SYSTEM_PDN_RUN_ID:-}"

mkdir -p "${OUT_DIR}" "${WORK}" "$(dirname "${REPORT}")" "$(dirname "${LOG}")"
: > "${LOG}"

if ! command -v ngspice >/dev/null 2>&1; then
  python3 - <<PY
import json
from pathlib import Path
out = {
  "kind": "system_pdn",
  "variant": "${VARIANT}",
  "engine": "ngspice-hierarchical",
  "ok": False,
  "status": "GAP",
  "reason": "ngspice is not installed; no hierarchical PDN measurement was executed",
  "summary": "GAP System PDN · ngspice unavailable"
}
Path("${REPORT}").write_text(json.dumps(out, indent=2) + "\n")
PY
  rm -f "${STAMP}"
  echo "SYSTEM_PDN_GAP ${VARIANT} · ngspice is not installed" | tee -a "${LOG}"
  exit 2
fi

[[ -f "${CFG}" ]] || { echo "FAIL missing config ${CFG}"; exit 1; }

# Prefer finished design if present (for current estimate); not strictly required
if [[ -f "${RES}/6_final.odb" ]]; then
  echo "=== System PDN · finish ODB present (${VARIANT}) ===" | tee -a "${LOG}"
else
  echo "=== System PDN · ODB missing — using I_DIE default/config ===" | tee -a "${LOG}"
fi

echo "=== Hierarchical System PDN (ngspice) · VRM→board→pkg→die ===" | tee -a "${LOG}"
EXTRA=()
if [[ "${I_DIE_AVG}" != "0" && -n "${I_DIE_AVG}" ]]; then
  EXTRA+=(--i-die "${I_DIE_AVG}")
fi
HIER_ARGS=()
if [[ -n "${HIER_RUN_ID}" ]]; then
  HIER_ARGS+=(--run-id "${HIER_RUN_ID}")
fi
if [[ -n "${HIER_RUN_DIR}" ]]; then
  HIER_ARGS+=(--run-dir "${HIER_RUN_DIR}")
fi

python3 "${ROOT}/learn/scripts/system_pdn_hier.py" \
  --config "${CFG}" \
  --out-dir "${WORK}" \
  --report "${REPORT}" \
  --repo "${ROOT}" \
  --variant "${VARIANT}" \
  "${HIER_ARGS[@]}" \
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

python3 "${ROOT}/learn/scripts/signoff_require_ok.py" "${REPORT}"
if [[ -n "${PD_FLOW_SYSTEM_PDN_STAMP:-}" || -z "${PD_FLOW_SYSTEM_PDN_REPORT:-}" ]]; then
  date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
fi
echo "SYSTEM_PDN_DONE ${VARIANT}" | tee -a "${LOG}"
echo "OK System PDN hierarchical ${VARIANT}"
echo "  log:    ${LOG}"
echo "  report: ${REPORT}"
echo "  work:   ${WORK}"
echo "Note: chip on-die IR → ./learn/scripts/run_chip_pdn_ir.sh"

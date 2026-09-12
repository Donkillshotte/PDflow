#!/usr/bin/env bash
# Convenience chain: activity → chip IR → System PDN → SPICE lab export.
#
# Not the four-pillar cook. power_signoff is chip-only. System PDN is PKG
# (run_system_pdn.sh / /pkg). This script still runs the ladder after chip IR
# so a single CLI can refresh both reports.
#
# Usage: run_power_chain.sh
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" power-chain bash "${BASH_SOURCE[0]}" "$@"
fi
VARIANT="${FLOW_VARIANT:-flowlab}"
LOG="${ROOT}/learn/sim/reports/power_chain_${VARIANT}.log"

mkdir -p "$(dirname "${LOG}")"
: > "${LOG}"

# Missing EDA dependencies are explicit GAPs.  Independent stages can still
# run, while unexpected failures remain fatal and visible.
CHAIN_GAP=0
run_step_or_gap() {
  local label="$1"
  shift
  local step_log
  local rc
  step_log="$(mktemp "${TMPDIR:-/tmp}/pdflow-power-chain.XXXXXX")"
  set +e
  "$@" 2>&1 | tee -a "${LOG}" | tee "${step_log}"
  rc="${PIPESTATUS[0]}"
  set -e
  if [[ "${rc}" -eq 0 ]]; then
    rm -f "${step_log}"
    return 0
  fi
  if grep -Eqi 'GAP|not installed|command not found|dependency|not available|FAIL missing|No such file or directory|cannot find' "${step_log}"; then
    echo "GAP ${label} · dependency or input unavailable; see ${LOG}" | tee -a "${LOG}"
    CHAIN_GAP=1
    rm -f "${step_log}"
    return 0
  fi
  echo "FAIL ${label} · exit ${rc}; see ${LOG}" | tee -a "${LOG}"
  rm -f "${step_log}"
  return "${rc}"
}

echo "=== POWER CHAIN START ${VARIANT} ===" | tee -a "${LOG}"

echo "--- 1/5 gate_sim ---" | tee -a "${LOG}"
if [[ -f "${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/6_final.v" ]]; then
  run_step_or_gap "gate_sim" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_gate_sim.sh"
else
  echo "skip gate_sim (no 6_final.v)" | tee -a "${LOG}"
fi

echo "--- 2/5 activity_power ---" | tee -a "${LOG}"
run_step_or_gap "activity_power" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_activity_power.sh"

echo "--- 3/5 chip_pdn_ir ---" | tee -a "${LOG}"
run_step_or_gap "chip_pdn_ir" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_chip_pdn_ir.sh"

echo "--- 4/5 system_pdn ---" | tee -a "${LOG}"
run_step_or_gap "system_pdn" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_system_pdn.sh"

echo "--- 5/5 export_spice_lab ---" | tee -a "${LOG}"
run_step_or_gap "export_spice_lab" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/export_spice_lab.sh"

python3 - <<PY | tee -a "${LOG}"
import json
from pathlib import Path
root = Path("${ROOT}")
v = "${VARIANT}"
rep = {}
for name, p in [
    ("activity", root / f"learn/sim/reports/activity_power_{v}.log"),
    ("chip_ir", root / f"learn/sim/reports/pdn_chip_ir_{v}.json"),
    ("system", root / f"learn/sim/reports/system_pdn_{v}.json"),
    ("mesh_stats", root / f"learn/sim/spice/mesh_stats_{v}.json"),
]:
    if p.exists():
        if p.suffix == ".json":
            rep[name] = json.loads(p.read_text())
        else:
            rep[name] = {"path": str(p), "bytes": p.stat().st_size}
print("CHAIN_SUMMARY", json.dumps({k: (v.get("summary") if isinstance(v, dict) and "summary" in v else "ok") for k,v in rep.items()}))
PY

if [[ "${CHAIN_GAP}" -eq 1 ]]; then
  echo "POWER_CHAIN_DONE ${VARIANT} status=GAP" | tee -a "${LOG}"
  echo "POWER_CHAIN_GAP ${VARIANT} · one or more stages were not verifiable" | tee -a "${LOG}"
else
  echo "POWER_CHAIN_DONE ${VARIANT} status=PASS" | tee -a "${LOG}"
fi
if [[ "${CHAIN_GAP}" -eq 1 ]]; then
  echo "COMPLETED power chain ${VARIANT} status=GAP"
else
  echo "COMPLETED power chain ${VARIANT} status=PASS"
fi
echo "  log: ${LOG}"

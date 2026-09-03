#!/usr/bin/env bash
# Full power integrity chain: activity → chip IR → System PDN → SPICE lab export.
#
# Requires finish (6_final.odb). Chains all post-PD SPICE analyses.
#
# Usage: run_power_chain.sh
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
LOG="${ROOT}/learn/sim/reports/power_chain_${VARIANT}.log"

mkdir -p "$(dirname "${LOG}")"
: > "${LOG}"

echo "=== POWER CHAIN START ${VARIANT} ===" | tee -a "${LOG}"

echo "--- 1/5 gate_sim ---" | tee -a "${LOG}"
if [[ -f "${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/6_final.v" ]]; then
  FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_gate_sim.sh" 2>&1 | tee -a "${LOG}" || echo "WARN gate_sim failed — activity falls back to RTL/synthetic" | tee -a "${LOG}"
else
  echo "skip gate_sim (no 6_final.v)" | tee -a "${LOG}"
fi

echo "--- 2/5 activity_power ---" | tee -a "${LOG}"
FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_activity_power.sh" 2>&1 | tee -a "${LOG}"

echo "--- 3/5 chip_pdn_ir ---" | tee -a "${LOG}"
FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_chip_pdn_ir.sh" 2>&1 | tee -a "${LOG}"

echo "--- 4/5 system_pdn ---" | tee -a "${LOG}"
FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_system_pdn.sh" 2>&1 | tee -a "${LOG}"

echo "--- 5/5 export_spice_lab ---" | tee -a "${LOG}"
FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/export_spice_lab.sh" 2>&1 | tee -a "${LOG}"

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

echo "POWER_CHAIN_DONE ${VARIANT}" | tee -a "${LOG}"
echo "OK power chain ${VARIANT}"
echo "  log: ${LOG}"

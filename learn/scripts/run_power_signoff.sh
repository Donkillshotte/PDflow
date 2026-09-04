#!/usr/bin/env bash
# Power signoff pillar: activity → chip IR → export + golden eval.
# System PDN (VRM→board→pkg) is PKG, after this close (/pkg).
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
OUT="${ROOT}/learn/sim/reports/power_signoff_${VARIANT}.json"
LOG="${ROOT}/learn/sim/reports/power_signoff_${VARIANT}.log"

mkdir -p "$(dirname "${OUT}")"
: > "${LOG}"

echo "=== POWER SIGNOFF ${VARIANT} ===" | tee -a "${LOG}"

FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_activity_power.sh" 2>&1 | tee -a "${LOG}"
FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_chip_pdn_ir.sh" 2>&1 | tee -a "${LOG}"
FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/export_spice_lab.sh" 2>&1 | tee -a "${LOG}"

python3 - <<PY | tee -a "${LOG}"
import json
from pathlib import Path
root = Path("${ROOT}")
v = "${VARIANT}"

def load_json(p):
    if not p.exists():
        return None
    return json.loads(p.read_text())

chip = load_json(root / f"learn/sim/reports/pdn_chip_ir_{v}.json") or {}

metrics = {
  "power": {
    "chip_static_ir_mv": float(chip.get("static", {}).get("worst_ir", 0) or 0) * 1e3,
    "chip_transient_droop_mv": float(chip.get("transient", {}).get("worst_droop", 0) or 0) * 1e3,
  }
}
mp = root / f"learn/sim/reports/.power_metrics_{v}.json"
mp.write_text(json.dumps(metrics, indent=2))
print("metrics", json.dumps(metrics["power"]))
PY

METRICS="${ROOT}/learn/sim/reports/.power_metrics_${VARIANT}.json"
python3 "${ROOT}/learn/scripts/signoff_eval.py" --pillar power --metrics "${METRICS}" --out "${OUT}.eval" --repo "${ROOT}" || true

python3 - <<PY | tee -a "${LOG}"
import json
from pathlib import Path
metrics = json.loads(Path("${METRICS}").read_text())
evald = json.loads(Path("${OUT}.eval").read_text()) if Path("${OUT}.eval").exists() else {}
pwr = metrics["power"]
ev = evald.get("pillars", {}).get("power", {})
out = {
  "kind": "power_signoff",
  "variant": "${VARIANT}",
  "power": pwr,
  "evaluation": ev,
  "ok": ev.get("ok"),
  "summary": (
      f"Chip IR {pwr['chip_static_ir_mv']:.2f} mV · "
      f"transient {pwr['chip_transient_droop_mv']:.2f} mV"
  ),
  "steps": ["activity_power", "chip_pdn_ir", "export_spice_lab"],
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("POWER_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
PY

python3 "${ROOT}/learn/scripts/ir_mesh_ledger.py" --variant "${VARIANT}" --stamp | tee -a "${LOG}"

echo "POWER_SIGNOFF_DONE ${VARIANT}"
python3 "${ROOT}/learn/scripts/signoff_require_ok.py" "${OUT}"

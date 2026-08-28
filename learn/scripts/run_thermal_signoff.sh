#!/usr/bin/env bash
# Thermal signoff proxy: IR heatmap + report_power → hotspot estimate (Fase 2)
# No HotSpot yet — educational proxy from existing power artifacts.
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
OUT="${ROOT}/learn/sim/reports/thermal_signoff_${VARIANT}.json"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
REPORTS="${FLOW}/reports/nangate45/gcd/${VARIANT}"
CHIP="${ROOT}/learn/sim/reports/pdn_chip_ir_${VARIANT}.json"

mkdir -p "$(dirname "${OUT}")"

IR_MV=0
DROOP_MV=0
HEATMAP=""
if [[ -f "${CHIP}" ]]; then
  read -r IR_MV DROOP_MV <<< "$(python3 - <<PY
import json
from pathlib import Path
c = json.loads(Path("${CHIP}").read_text())
ir = float(c.get("static", {}).get("worst_ir", 0) or 0) * 1e3
dr = float(c.get("transient", {}).get("worst_droop", 0) or 0) * 1e3
print(ir, dr)
PY
)"
fi
for f in "${REPORTS}"/orfs_final_ir_drop.png "${REPORTS}"/final_ir_drop.png; do
  [[ -f "${f}" ]] && HEATMAP="${f}" && break
done

# Proxy: worst-case mV from chip IR + droop; flag if combined > 50 mV (educational)
COMBINED="$(python3 - <<PY
ir, dr = float("${IR_MV}"), float("${DROOP_MV}")
print(ir + dr)
PY
)"
PROXY_OK="$(python3 - <<PY
print("true" if float("${COMBINED}") <= 50.0 else "false")
PY
)"

python3 - <<PY
import json
from pathlib import Path
proxy_ok = "${PROXY_OK}" == "true"
out = {
  "kind": "thermal_signoff",
  "variant": "${VARIANT}",
  "status": "proxy",
  "thermal": {
    "chip_ir_mv": float("${IR_MV}"),
    "chip_droop_mv": float("${DROOP_MV}"),
    "combined_proxy_mv": float("${COMBINED}"),
    "heatmap_png": "${HEATMAP}" or None,
    "note": "Proxy from chip IR + droop; HotSpot/3D-ICE planned for full thermal",
  },
  "evaluation": {
    "checks": [{
      "id": "combined_proxy_mv",
      "label": "Combined IR+droop proxy (mV)",
      "actual": float("${COMBINED}"),
      "target": 50.0,
      "ok": proxy_ok,
    }],
    "ok": proxy_ok,
  },
  "ok": proxy_ok,
  "summary": f"Thermal proxy {float('${COMBINED}'):.2f} mV (IR {float('${IR_MV}'):.2f} + droop {float('${DROOP_MV}'):.2f})",
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("THERMAL_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
PY

echo "THERMAL_SIGNOFF_DONE ${VARIANT}"

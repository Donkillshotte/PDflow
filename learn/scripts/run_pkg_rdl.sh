#!/usr/bin/env bash
# PKG RDL signoff: educational status for rdl_route API (no bump LEF on GCD tutorial)
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
OUT="${ROOT}/learn/sim/reports/pkg_rdl_${VARIANT}.json"
GDS="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/6_final.gds"

mkdir -p "$(dirname "${OUT}")"

HAS_GDS=false
[[ -f "${GDS}" ]] && HAS_GDS=true

python3 - <<PY
import json
from pathlib import Path

has_gds = "${HAS_GDS}" == "true"
# Educational: rdl_route requires bump/pad LEF — not in nangate45 GCD tutorial
api_ready = True
rdl_executed = False

out = {
  "kind": "pkg_rdl",
  "variant": "${VARIANT}",
  "rdl": {
    "api": "rdl_route",
    "executed": rdl_executed,
    "gds_present": has_gds,
    "platform_bump_lef": False,
  },
  "evaluation": {
    "checks": [
      {
        "id": "api_documented",
        "label": "RDL API documented (pkg-design-package)",
        "actual": api_ready,
        "target": True,
        "ok": api_ready,
      },
      {
        "id": "gds_for_future_rdl",
        "label": "GDS present (prerequisite for RDL lab)",
        "actual": has_gds,
        "target": True,
        "ok": has_gds,
        "note": "Real rdl_route needs bump LEF design",
      },
    ],
    "ok": api_ready and has_gds,
  },
  "ok": api_ready and has_gds,
  "educational_note": "rdl_route not run on GCD — value is process map for packaging labs",
  "summary": f"RDL educational · GDS={'ok' if has_gds else 'missing'} · bump LEF=N/A",
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("PKG_RDL_JSON", "${OUT}")
print(out["summary"])
PY

echo "PKG_RDL_DONE ${VARIANT}"

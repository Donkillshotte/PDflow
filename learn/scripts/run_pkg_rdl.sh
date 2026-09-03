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
# Honest GAP: rdl_route needs bump/pad LEF — Nangate45 GCD tutorial has none.
# Documented API is not a pass. Do not set ok true because GDS exists.
rdl_executed = False
has_bump_lef = False

out = {
  "kind": "pkg_rdl",
  "variant": "${VARIANT}",
  "status": "GAP",
  "rdl": {
    "api": "rdl_route",
    "executed": rdl_executed,
    "gds_present": has_gds,
    "platform_bump_lef": has_bump_lef,
  },
  "evaluation": {
    "checks": [
      {
        "id": "rdl_executed",
        "label": "rdl_route executed",
        "actual": rdl_executed,
        "target": True,
        "ok": False,
        "note": "Nangate45 GCD has no bump/pad LEF; rdl_route is not run",
      },
      {
        "id": "platform_bump_lef",
        "label": "Platform bump LEF",
        "actual": has_bump_lef,
        "target": True,
        "ok": False,
      },
      {
        "id": "gds_for_future_rdl",
        "label": "GDS present (prerequisite for an RDL lab)",
        "actual": has_gds,
        "target": True,
        "ok": has_gds,
        "note": "Prerequisite only — does not make RDL pass",
      },
    ],
    "ok": False,
  },
  "ok": False,
  "educational_note": "rdl_route not executed on GCD. GAP, not a mock pass. See pkg-design-package.md.",
  "summary": (
      f"RDL GAP · rdl_route not executed · bump LEF=N/A · "
      f"GDS={'ok' if has_gds else 'missing'}"
  ),
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("PKG_RDL_JSON", "${OUT}")
print(out["summary"])
PY

echo "PKG_RDL_DONE ${VARIANT}"

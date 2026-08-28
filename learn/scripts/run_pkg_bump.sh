#!/usr/bin/env bash
# PKG bump signoff: extract bump pattern from system PDN config + chip mesh SPICE
# Educational — Nangate45 GCD has no bump LEF; documents package model + mesh sources.
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
OUT="${ROOT}/learn/sim/reports/pkg_bump_${VARIANT}.json"
CONFIG="${ROOT}/learn/system_pdn/default.json"
MESH="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/pdn/pg_vdd_bumps.sp"
ALT_MESH="${ROOT}/learn/sim/spice/pg_vdd_bumps_${VARIANT}.sp"

mkdir -p "$(dirname "${OUT}")"

python3 - <<PY
import json
from pathlib import Path

root = Path("${ROOT}")
variant = "${VARIANT}"
config = json.loads(Path("${CONFIG}").read_text())
pkg = config.get("package", {})
mesh = Path("${MESH}")
if not mesh.exists():
    mesh = Path("${ALT_MESH}")

v_sources = 0
r_count = 0
if mesh.exists():
    text = mesh.read_text()
    v_sources = sum(1 for line in text.splitlines() if line.strip().startswith("V"))
    r_count = sum(1 for line in text.splitlines() if line.strip().startswith("R"))

n_bumps_cfg = int(pkg.get("n_bumps", 0))
ok = n_bumps_cfg > 0 and (mesh.exists() or v_sources > 0)

out = {
  "kind": "pkg_bump",
  "variant": variant,
  "package": {
    "n_bumps": n_bumps_cfg,
    "r_bump": pkg.get("r_bump"),
    "l_bump": pkg.get("l_bump"),
    "r_pkg": pkg.get("r_pkg"),
    "l_pkg": pkg.get("l_pkg"),
  },
  "mesh": {
    "path": str(mesh) if mesh.exists() else None,
    "v_sources": v_sources,
    "r_elements": r_count,
  },
  "evaluation": {
    "checks": [
      {
        "id": "n_bumps",
        "label": "Package bump count (config)",
        "actual": n_bumps_cfg,
        "target": 1,
        "ok": n_bumps_cfg >= 1,
      },
      {
        "id": "mesh_spice",
        "label": "Chip mesh SPICE (write_pg_spice)",
        "actual": mesh.exists(),
        "target": True,
        "ok": mesh.exists(),
        "note": "Run chip_pdn_ir after finish if mesh missing",
      },
    ],
    "ok": ok,
  },
  "ok": ok,
  "educational_note": "GCD has synthetic BUMPS pattern (PSM-0073), not tapeout bump LEF",
  "summary": f"Bumps {n_bumps_cfg} · mesh V={v_sources} R={r_count}",
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("PKG_BUMP_JSON", "${OUT}")
print(out["summary"])
PY

echo "PKG_BUMP_DONE ${VARIANT}"

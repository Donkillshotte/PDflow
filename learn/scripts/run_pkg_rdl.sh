#!/usr/bin/env bash
# PKG RDL: OpenROAD rdl_route on a sidecar ODB + scaled dummy bump LEF.
# Never writes into gcd/{flowlab,learn}/6_final.odb.
# ok is true only if the router wrote RDL wires.
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
OUT="${ROOT}/learn/sim/reports/pkg_rdl_${VARIANT}.json"
LOG="${ROOT}/learn/sim/reports/pkg_rdl_${VARIANT}.log"
RES="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}"
ODB="${RES}/6_final.odb"
GDS="${RES}/6_final.gds"
LEF="${ROOT}/learn/platforms/nangate45/pkg/dummy_bump_gcd.lef"
SIDE="${RES}/pkg_rdl_sidecar"
TCL="${ROOT}/learn/scripts/pkg_rdl_sidecar.tcl"

mkdir -p "$(dirname "${OUT}")" "${SIDE}"
: > "${LOG}"

HAS_GDS=false
[[ -f "${GDS}" ]] && HAS_GDS=true
HAS_LEF=false
[[ -f "${LEF}" ]] && HAS_LEF=true

if [[ ! -f "${ODB}" ]]; then
  python3 - <<PY
import json
from pathlib import Path
out = {
  "kind": "pkg_rdl",
  "variant": "${VARIANT}",
  "status": "GAP",
  "ok": False,
  "rdl": {"api": "rdl_route", "executed": False, "gds_present": "${HAS_GDS}" == "true", "platform_bump_lef": "${HAS_LEF}" == "true"},
  "summary": "RDL GAP · missing 6_final.odb",
  "educational_note": "dummy bump LEF, not C4",
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\n")
print(out["summary"])
PY
  echo "PKG_RDL_DONE ${VARIANT}"
  exit 1
fi

cp -f "${ODB}" "${SIDE}/in.odb"
export RDL_ODB="${SIDE}/in.odb"
export RDL_LEF="${LEF}"
export RDL_OUT_ODB="${SIDE}/rdl.odb"
export RDL_OUT_DEF="${SIDE}/rdl.def"
export RDL_STATS="${SIDE}/rdl_stats.json"
export RDL_LAYER="${RDL_LAYER:-metal10}"
export RDL_WIDTH="${RDL_WIDTH:-0.8}"
export RDL_SPACING="${RDL_SPACING:-0.8}"

set +e
openroad -no_init -no_splash -exit "${TCL}" >> "${LOG}" 2>&1
OR_RC=$?
set -e

python3 - <<PY
import json, re
from pathlib import Path

log = Path("${LOG}").read_text(errors="replace")
defn = Path("${RDL_OUT_DEF}")
has_gds = "${HAS_GDS}" == "true"
has_lef = "${HAS_LEF}" == "true"
n_metal10 = n_metal6 = n_bump = 0
n_wires = 0
if defn.is_file():
    text = defn.read_text(errors="replace")
    n_bump = len(re.findall(r"\bDUMMY_BUMP\b", text))
    n_metal10 = len(re.findall(r"ROUTED metal10|NEW metal10", text))
    n_metal6 = len(re.findall(r"ROUTED metal6|NEW metal6", text))
    n_wires = n_metal10 + n_metal6

# ok only if the sidecar DEF contains RDL wires the router wrote.
executed = bool(defn.is_file() and n_bump > 0 and n_wires > 0)

ok = executed
status = "READY" if ok else "GAP"
note = (
    "dummy bump LEF (scaled OpenROAD pad test), not C4. "
    "Sidecar ODB only — FlowLab 6_final.odb is untouched. "
    "metal10 bump-to-bump plus metal6 pin fallback (GCD pins are M5/M6)."
)
out = {
  "kind": "pkg_rdl",
  "variant": "${VARIANT}",
  "status": status,
  "rdl": {
    "api": "rdl_route",
    "executed": executed,
    "gds_present": has_gds,
    "platform_bump_lef": has_lef,
    "sidecar_odb": "${RDL_OUT_ODB}" if Path("${RDL_OUT_ODB}").is_file() else None,
    "sidecar_def": str(defn) if defn.is_file() else None,
    "n_dummy_bump": n_bump,
    "n_rdl_wires": n_wires,
    "n_metal10_tokens": n_metal10,
    "openroad_rc": int("${OR_RC}"),
    "log": "${LOG}",
  },
  "evaluation": {
    "checks": [
      {
        "id": "rdl_executed",
        "label": "rdl_route executed and wrote wires",
        "actual": executed,
        "target": True,
        "ok": executed,
        "note": "ok only when the router wrote metal10/metal6 wires on the sidecar",
      },
      {
        "id": "platform_bump_lef",
        "label": "Educational dummy bump LEF",
        "actual": has_lef,
        "target": True,
        "ok": has_lef,
      },
      {
        "id": "sidecar_not_baseline",
        "label": "Sidecar ODB (baseline untouched)",
        "actual": True,
        "target": True,
        "ok": True,
      },
    ],
    "ok": ok,
  },
  "ok": ok,
  "educational_note": note,
  "summary": (
      f"RDL {'READY' if ok else 'GAP'} · executed={executed} · "
      f"bumps={n_bump} · wires={n_wires} · dummy LEF, not C4"
  ),
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\n")
print("PKG_RDL_JSON", "${OUT}")
print(out["summary"])
if not ok:
    raise SystemExit(1)
PY

echo "PKG_RDL_DONE ${VARIANT}"

#!/usr/bin/env bash
# PKG RDL: OpenROAD rdl_route on a sidecar ODB + scaled dummy bump LEF.
# Never writes into gcd/{flowlab,learn}/6_final.odb.
# The router output is useful package evidence, but the dummy bump LEF is not
# a tapeout package model. A successful run is therefore PROXY/ok=false.
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" pkg-rdl bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
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
  "evidence_ok": False,
  "product_signoff": False,
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
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path("${ROOT}") / "learn" / "scripts"))
from pkg_manifest import _configured_interface, parse_bump_components, parse_rdl, read_json

log = Path("${LOG}").read_text(errors="replace")
defn = Path("${RDL_OUT_DEF}")
has_gds = "${HAS_GDS}" == "true"
has_lef = "${HAS_LEF}" == "true"
n_metal10 = n_metal6 = n_bump = 0
n_wires = 0
routed_nets = []
missing_nets = []
if defn.is_file():
    text = defn.read_text(errors="replace")
    n_bump = len(parse_bump_components(text))
    cfg = read_json(Path("${ROOT}") / "learn" / "system_pdn" / "default.json") or {}
    array, configured = _configured_interface(cfg)
    rdl_layers = {
        str(array.get("power_layer") or ""),
        str(array.get("signal_layer") or ""),
    }
    rdl_layers.discard("")
    parsed = parse_rdl(text, rdl_layers=rdl_layers)
    for row in parsed["nets"]:
        n_metal10 += sum(1 for layer in row["route_layers"] if layer == "metal10")
        n_metal6 += sum(1 for layer in row["route_layers"] if layer == "metal6")
    n_wires = parsed["route_segments"]
    required = sorted({row["net"] for row in configured if row["class"] != "reserved"})
    routed_nets = sorted(row["net"] for row in parsed["nets"] if row["net"] in required and row["routed"])
    missing_nets = sorted(set(required) - set(routed_nets))

# Evidence is valid only when every configured package net has a routed
# SPECIALNET entry. Counting arbitrary metal6 routes in the chip NETS section
# would make an incomplete RDL sidecar look successful.
executed = bool(defn.is_file() and n_bump > 0 and n_wires > 0 and not missing_nets)

evidence_ok = executed
status = "PROXY" if executed else "GAP"
note = (
    "dummy bump LEF (scaled OpenROAD pad test), not C4. "
    "Sidecar ODB only — FlowLab 6_final.odb is untouched. "
    "metal10 bump-to-bump plus metal6 pin fallback (GCD pins are M5/M6)."
)
out = {
  "kind": "pkg_rdl",
  "variant": "${VARIANT}",
  "status": status,
  "ok": False,
  "evidence_ok": evidence_ok,
  "product_signoff": False,
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
    "routed_nets": routed_nets,
    "missing_nets": missing_nets,
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
        "ok": False,
        "evidence_ok": executed,
        "note": "PROXY: router wrote wires on an educational dummy-bump sidecar",
      },
      {
        "id": "platform_bump_lef",
        "label": "Educational dummy bump LEF",
        "actual": has_lef,
        "target": True,
        "ok": has_lef,
      },
      {
        "id": "sidecar_current_finish_untouched",
        "label": "Sidecar ODB (current finish untouched)",
        "actual": True,
        "target": True,
        "ok": True,
      },
    ],
    "ok": False,
    "evidence_ok": evidence_ok,
  },
  "ok": False,
  "evidence_ok": evidence_ok,
  "product_signoff": False,
  "educational_note": note,
  "summary": (
      f"RDL {'PROXY' if executed else 'GAP'} · executed={executed} · "
      f"bumps={n_bump} · wires={n_wires} · dummy LEF, not C4"
  ),
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\n")
print("PKG_RDL_JSON", "${OUT}")
print(out["summary"])
if not evidence_ok:
    raise SystemExit(1)
PY

echo "PKG_RDL_DONE ${VARIANT}"

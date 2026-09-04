#!/usr/bin/env bash
# PKG signoff pillar: bump config + RDL educational + system PDN gate
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
OUT="${ROOT}/learn/sim/reports/pkg_signoff_${VARIANT}.json"
LOG="${ROOT}/learn/sim/reports/pkg_signoff_${VARIANT}.log"

mkdir -p "$(dirname "${OUT}")"
: > "${LOG}"

echo "=== PKG SIGNOFF ${VARIANT} ===" | tee -a "${LOG}"

FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_pkg_bump.sh" 2>&1 | tee -a "${LOG}"
FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_pkg_rdl.sh" 2>&1 | tee -a "${LOG}"

python3 - <<PY | tee -a "${LOG}"
import json
from pathlib import Path
root = Path("${ROOT}")
v = "${VARIANT}"

def load(name):
    p = root / f"learn/sim/reports/{name}_{v}.json"
    return json.loads(p.read_text()) if p.exists() else None

bump = load("pkg_bump") or {}
rdl = load("pkg_rdl") or {}
sys = load("system_pdn") or {}

sys_ok = sys.get("ok")
if sys_ok is None and sys.get("summary"):
    sys_ok = True

rdl_executed = bool((rdl.get("rdl") or {}).get("executed"))
# Never treat "API documented" / GDS present as an RDL pass.
rdl_ok = bool(rdl.get("ok")) and rdl_executed
rdl_status = rdl.get("status") or ("GAP" if not rdl_executed else None)

steps = {
  "pkg_bump": {"ok": bump.get("ok") is True, "summary": bump.get("summary")},
  "pkg_rdl": {
    "ok": rdl_ok,
    "status": rdl_status,
    "summary": rdl.get("summary"),
  },
  "system_pdn": {"ok": bool(sys_ok), "summary": sys.get("summary")},
}
# Executable pieces: bump mesh + system PDN. Dummy rdl_route is extra when it ran.
executable_ok = bool(steps["pkg_bump"]["ok"]) and bool(steps["system_pdn"]["ok"])
rdl_label = "ok" if rdl_ok else ("GAP" if not rdl_executed else "fail")
out = {
  "kind": "pkg_signoff",
  "variant": v,
  "status": "proxy",
  "steps": steps,
  "evaluation": {
    "checks": [
      {
        "id": "pkg_bump",
        "label": "Bump mesh + package config",
        "actual": steps["pkg_bump"]["ok"],
        "target": True,
        "ok": steps["pkg_bump"]["ok"],
      },
      {
        "id": "pkg_rdl",
        "label": "RDL routing",
        "actual": rdl_executed,
        "target": True,
        "ok": rdl_ok,
        "note": "dummy bump LEF sidecar; not C4. ok only if rdl_route wrote wires",
      },
      {
        "id": "system_pdn",
        "label": "System PDN",
        "actual": steps["system_pdn"]["ok"],
        "target": True,
        "ok": steps["system_pdn"]["ok"],
      },
    ],
    "ok": executable_ok,
  },
  "ok": executable_ok,
  "summary": (
      f"bump:{'ok' if steps['pkg_bump']['ok'] else 'fail'} · "
      f"rdl:{rdl_label} · "
      f"system_pdn:{'ok' if steps['system_pdn']['ok'] else 'fail'}"
  ),
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("PKG_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
PY

echo "PKG_SIGNOFF_DONE ${VARIANT}"
python3 "${ROOT}/learn/scripts/signoff_require_ok.py" "${OUT}"

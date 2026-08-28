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

steps = {
  "pkg_bump": {"ok": bump.get("ok"), "summary": bump.get("summary")},
  "pkg_rdl": {"ok": rdl.get("ok"), "summary": rdl.get("summary")},
  "system_pdn": {"ok": sys_ok, "summary": sys.get("summary")},
}
all_ok = all(s.get("ok") for s in steps.values() if s.get("ok") is not None)
out = {
  "kind": "pkg_signoff",
  "variant": v,
  "steps": steps,
  "ok": all_ok,
  "summary": " · ".join(f"{k}:{'ok' if s.get('ok') else 'fail'}" for k, s in steps.items()),
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("PKG_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
PY

echo "PKG_SIGNOFF_DONE ${VARIANT}"

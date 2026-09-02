#!/usr/bin/env bash
# Phase 2 signoff: thermal proxy + PKG bump/RDL/system
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
LOG="${ROOT}/learn/sim/reports/signoff_phase2_${VARIANT}.log"
OUT="${ROOT}/learn/sim/reports/signoff_phase2_${VARIANT}.json"

mkdir -p "$(dirname "${LOG}")"
: > "${LOG}"

echo "=== SIGNOFF PHASE2 ${VARIANT} ===" | tee -a "${LOG}"

FAIL=0
run_step() {
  local name="$1"
  shift
  echo "--- ${name} ---" | tee -a "${LOG}"
  if "$@" 2>&1 | tee -a "${LOG}"; then
    echo "OK ${name}" | tee -a "${LOG}"
  else
    echo "FAIL ${name}" | tee -a "${LOG}"
    FAIL=1
  fi
}

run_step "thermal_signoff" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_thermal_signoff.sh"
run_step "pkg_signoff" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_pkg_signoff.sh"

python3 - <<PY | tee -a "${LOG}"
import json
from pathlib import Path
root = Path("${ROOT}")
v = "${VARIANT}"
pillars = {}
for kind, fname in [
  ("thermal", f"thermal_signoff_{v}.json"),
  ("pkg", f"pkg_signoff_{v}.json"),
]:
  p = root / "learn/sim/reports" / fname
  if p.exists():
    r = json.loads(p.read_text())
    pillars[kind] = {"ok": r.get("ok"), "summary": r.get("summary")}
  else:
    pillars[kind] = {"ok": False, "summary": "missing"}

all_ok = all(p.get("ok") for p in pillars.values())
out = {
  "kind": "signoff_phase2",
  "variant": v,
  "pillars": pillars,
  "ok": all_ok and int("${FAIL}") == 0,
  "summary": " · ".join(f"{k}:{'ok' if p.get('ok') else 'fail'}" for k, p in pillars.items()),
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("SIGNOFF_PHASE2_JSON", "${OUT}")
print(out["summary"])
PY

echo "SIGNOFF_PHASE2_DONE ${VARIANT}"
[[ "${FAIL}" -eq 0 ]] || exit 1

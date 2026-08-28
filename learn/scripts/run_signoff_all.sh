#!/usr/bin/env bash
# Full signoff: STA → DRC → LVS → Power (sequential)
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
LOG="${ROOT}/learn/sim/reports/signoff_all_${VARIANT}.log"
OUT="${ROOT}/learn/sim/reports/signoff_all_${VARIANT}.json"

mkdir -p "$(dirname "${LOG}")"
: > "${LOG}"

echo "=== SIGNOFF ALL ${VARIANT} ===" | tee -a "${LOG}"

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

run_step "sta_signoff" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_sta_signoff.sh"
run_step "drc_signoff" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_drc_signoff.sh"
run_step "klayout_lvs" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_klayout_lvs.sh"
run_step "power_signoff" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_power_signoff.sh"

python3 - <<PY | tee -a "${LOG}"
import json
from pathlib import Path
root = Path("${ROOT}")
v = "${VARIANT}"
pillars = {}
for kind, fname in [
  ("timing", f"sta_signoff_{v}.json"),
  ("geometry", f"drc_signoff_{v}.json"),
  ("equivalence", f"lvs_signoff_{v}.json"),
  ("power", f"power_signoff_{v}.json"),
]:
  p = root / "learn/sim/reports" / fname
  if p.exists():
    r = json.loads(p.read_text())
    pillars[kind] = {"ok": r.get("ok"), "summary": r.get("summary")}
  else:
    pillars[kind] = {"ok": False, "summary": "missing"}

all_ok = all(p.get("ok") for p in pillars.values() if p.get("ok") is not None)
out = {
  "kind": "signoff_all",
  "variant": v,
  "pillars": pillars,
  "ok": all_ok and int("${FAIL}") == 0,
  "summary": " · ".join(f"{k}:{'ok' if p.get('ok') else 'fail'}" for k, p in pillars.items()),
}
out_path = Path("${OUT}")
out_path.write_text(json.dumps(out, indent=2) + "\\n")
print("SIGNOFF_ALL_JSON", out_path)
print(out["summary"])
PY

echo "SIGNOFF_ALL_DONE ${VARIANT}"
[[ "${FAIL}" -eq 0 ]] || exit 1

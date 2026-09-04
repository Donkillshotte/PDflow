#!/usr/bin/env bash
# Full signoff: STA → DRC → LVS → Power (sequential)
# Optional Phase 2: SIGNOFF_INCLUDE_PHASE2=1 → thermal + PKG after phase 1
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
INCLUDE_PHASE2="${SIGNOFF_INCLUDE_PHASE2:-0}"
LOG="${ROOT}/learn/sim/reports/signoff_all_${VARIANT}.log"
OUT="${ROOT}/learn/sim/reports/signoff_all_${VARIANT}.json"

mkdir -p "$(dirname "${LOG}")"
: > "${LOG}"

echo "=== SIGNOFF ALL ${VARIANT} (phase2=${INCLUDE_PHASE2}) ===" | tee -a "${LOG}"

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

if [[ "${INCLUDE_PHASE2}" == "1" ]]; then
  run_step "signoff_phase2" env FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_signoff_phase2.sh"
fi

python3 "${ROOT}/learn/scripts/stamp_signoff_all.py" --variant "${VARIANT}" --stamp | tee -a "${LOG}"
if ! python3 "${ROOT}/learn/scripts/signoff_require_ok.py" "${OUT}"; then
  echo "FAIL signoff_all JSON ok is not true" | tee -a "${LOG}"
  FAIL=1
fi
if [[ "${INCLUDE_PHASE2}" == "1" ]]; then
  python3 - <<PY | tee -a "${LOG}"
import json
from pathlib import Path
root = Path("${ROOT}")
v = "${VARIANT}"
out_path = root / "learn/sim/reports" / f"signoff_all_{v}.json"
blob = json.loads(out_path.read_text()) if out_path.is_file() else {"kind": "signoff_all", "variant": v}
phase2 = {}
for kind, fname in (("thermal", f"thermal_signoff_{v}.json"), ("pkg", f"pkg_signoff_{v}.json")):
    p = root / "learn/sim/reports" / fname
    if p.exists():
        r = json.loads(p.read_text())
        phase2[kind] = {"ok": r.get("ok"), "summary": r.get("summary")}
    else:
        phase2[kind] = {"ok": False, "summary": "missing"}
blob["phase2_pillars"] = phase2
blob["include_phase2"] = True
if not all(p.get("ok") for p in phase2.values()):
    blob["ok"] = False
blob["summary"] = blob.get("summary", "") + " · " + " · ".join(
    f"{k}:{'ok' if p.get('ok') else 'fail'}" for k, p in phase2.items()
)
out_path.write_text(json.dumps(blob, indent=2) + "\\n")
print("SIGNOFF_ALL_JSON", out_path)
print(blob["summary"])
PY
fi
if [[ "${FAIL}" -ne 0 ]]; then
  python3 - <<PY
import json
from pathlib import Path
p = Path("${OUT}")
if p.is_file():
    blob = json.loads(p.read_text())
    blob["ok"] = False
    p.write_text(json.dumps(blob, indent=2) + "\\n")
PY
fi

echo "SIGNOFF_ALL_DONE ${VARIANT}"
[[ "${FAIL}" -eq 0 ]] || exit 1

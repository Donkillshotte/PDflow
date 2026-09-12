#!/usr/bin/env bash
# Phase 2 signoff: thermal proxy + PKG bump/RDL/system
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" signoff-phase2 bash "${BASH_SOURCE[0]}" "$@"
fi
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

def canonical_status(report):
  raw = str(report.get("status") or "").upper()
  if raw in {"PASS", "FAIL", "WARN", "PARTIAL", "PROXY", "GAP", "NOT_RUN"}:
    return raw
  if report.get("ok") is True:
    return "PASS"
  if report.get("ok") is False:
    return "FAIL"
  return "NOT_RUN"

for kind, fname in [
  ("thermal", f"thermal_signoff_{v}.json"),
  ("pkg", f"pkg_signoff_{v}.json"),
]:
  p = root / "learn/sim/reports" / fname
  if p.exists():
    r = json.loads(p.read_text())
    status = canonical_status(r)
    pillars[kind] = {
      "status": status,
      "ok": r.get("ok") is True and status == "PASS",
      "summary": r.get("summary"),
    }
  else:
    pillars[kind] = {"status": "NOT_RUN", "ok": False, "summary": "missing"}

statuses = {p["status"] for p in pillars.values()}
if "GAP" in statuses or "NOT_RUN" in statuses:
  overall_status = "GAP"
elif "FAIL" in statuses:
  overall_status = "FAIL"
elif "PARTIAL" in statuses:
  overall_status = "PARTIAL"
elif "PROXY" in statuses:
  overall_status = "PROXY"
else:
  overall_status = "PASS"
all_ok = overall_status == "PASS" and all(p.get("ok") for p in pillars.values())
evidence_ok = int("${FAIL}") == 0 and all(
  p.get("status") not in {"GAP", "FAIL", "NOT_RUN"}
  for p in pillars.values()
)
out = {
  "kind": "signoff_phase2",
  "variant": v,
  "pillars": pillars,
  "status": overall_status,
  "ok": all_ok and int("${FAIL}") == 0,
  "evidence_ok": evidence_ok,
  "product_signoff": all_ok and int("${FAIL}") == 0,
  "summary": " · ".join(f"{k}:{p.get('status', 'NOT_RUN').lower()}" for k, p in pillars.items()),
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("SIGNOFF_PHASE2_JSON", "${OUT}")
print(out["summary"])
PY

echo "SIGNOFF_PHASE2_DONE ${VARIANT}"
if [[ "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status", "FAIL"))' "${OUT}")" == "PROXY" ]]; then
  echo "OK phase-two evidence generated · PROXY is not Product signoff" | tee -a "${LOG}"
else
  python3 "${ROOT}/learn/scripts/signoff_require_ok.py" "${OUT}" || FAIL=1
fi
[[ "${FAIL}" -eq 0 ]] || exit 1

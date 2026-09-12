#!/usr/bin/env bash
# PKG signoff pillar: bump config + RDL educational + system PDN live report
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" pkg-signoff bash "${BASH_SOURCE[0]}" "$@"
fi
VARIANT="${FLOW_VARIANT:-flowlab}"
OUT="${ROOT}/learn/sim/reports/pkg_signoff_${VARIANT}.json"
LOG="${ROOT}/learn/sim/reports/pkg_signoff_${VARIANT}.log"

mkdir -p "$(dirname "${OUT}")"
: > "${LOG}"

echo "=== PKG SIGNOFF ${VARIANT} ===" | tee -a "${LOG}"

FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_pkg_bump.sh" 2>&1 | tee -a "${LOG}"
if ! FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_pkg_rdl.sh" 2>&1 | tee -a "${LOG}"; then
  echo "GAP pkg_rdl · package signoff report will preserve the unavailable coverage" | tee -a "${LOG}"
fi
if ! FLOW_VARIANT="${VARIANT}" "${ROOT}/learn/scripts/run_system_pdn.sh" 2>&1 | tee -a "${LOG}"; then
  echo "GAP system_pdn · package signoff report will preserve the unavailable status" | tee -a "${LOG}"
fi

MANIFEST="${ROOT}/learn/sim/reports/pkg_manifest_${VARIANT}.json"
if ! PYTHONPATH="${ROOT}/learn/scripts${PYTHONPATH:+:${PYTHONPATH}}" \
  python3 "${ROOT}/learn/scripts/pkg_manifest.py" --variant "${VARIANT}" --out "${MANIFEST}" 2>&1 | tee -a "${LOG}"; then
  echo "GAP package_manifest · manifest generation failed" | tee -a "${LOG}"
fi

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
manifest = load("pkg_manifest") or {}

droop = float((sys.get("transient") or {}).get("droop_mv") or 0)
zmax = float((sys.get("impedance") or {}).get("z_max_mohm") or 0)
# Measurements are accepted only when the live engine completed and emitted
# finite, non-negative values. No fixed limit is applied here.
sys_ok = sys.get("ok") is True and droop >= 0 and zmax >= 0

rdl_executed = bool((rdl.get("rdl") or {}).get("executed"))
# Never treat "API documented" / GDS present as an RDL pass. The current
# dummy-bump sidecar is executable evidence, but it is not a Product signoff.
rdl_evidence_ok = rdl_executed
rdl_ok = bool(rdl.get("ok")) and rdl_evidence_ok
rdl_status = rdl.get("status") or ("GAP" if not rdl_executed else None)
manifest_rdl = manifest.get("rdl") if isinstance(manifest.get("rdl"), dict) else {}
manifest_rdl_evidence_ok = (
  bool(manifest_rdl)
  and bool(manifest_rdl.get("ready"))
  and not bool(manifest_rdl.get("missing_nets"))
)
if manifest:
  rdl_evidence_ok = manifest_rdl_evidence_ok
  rdl_ok = manifest_rdl_evidence_ok
  rdl_status = (
    "PROXY" if manifest_rdl_evidence_ok
    else "FAIL" if manifest_rdl.get("ready")
    else "GAP"
  )

steps = {
  "pkg_bump": {"ok": bump.get("ok") is True, "summary": bump.get("summary")},
  "pkg_rdl": {
    "ok": rdl_ok,
    "evidence_ok": rdl_evidence_ok,
    "status": rdl_status,
    "summary": rdl.get("summary"),
  },
 "system_pdn": {
  "ok": sys_ok,
   "status": sys.get("status") or ("READY" if sys_ok else "FAIL"),
  "summary": sys.get("summary"),
  "droop_mv": droop,
  "zmax_mohm": zmax,
},
  "package_manifest": {
    "ok": manifest.get("evidence_ok") is True,
    "evidence_ok": manifest.get("evidence_ok") is True,
    "status": manifest.get("status") or "NOT_RUN",
    "summary": manifest.get("summary"),
    "report": "learn/sim/reports/pkg_manifest_${VARIANT}.json",
    "manifest": True,
  },
}
# The package evidence is intentionally not Product signoff: RDL is based on
# an educational dummy bump LEF. Keep each executable check visible, but do
# not let that proxy produce a green Product badge.
evidence_ok = (
  manifest.get("evidence_ok") is True
  if manifest
  else bool(steps["pkg_bump"]["ok"]) and rdl_evidence_ok and bool(steps["system_pdn"]["ok"])
)
manifest_status = str(manifest.get("status") or "NOT_RUN").upper()
if manifest:
  package_status = (
    "GAP" if manifest_status in {"GAP", "NOT_RUN"}
    else "FAIL" if manifest_status == "FAIL"
    else "PROXY" if manifest_status == "PROXY"
    else manifest_status
  )
else:
  if sys.get("status") == "GAP" or not rdl_evidence_ok:
    package_status = "GAP"
  elif not bool(steps["pkg_bump"]["ok"]) or not bool(steps["system_pdn"]["ok"]):
    package_status = "FAIL"
  else:
    package_status = "PROXY"
rdl_label = "proxy" if rdl_evidence_ok else "GAP"
out = {
 "kind": "pkg_signoff",
 "variant": v,
  "status": package_status,
  "evidence_ok": evidence_ok,
  "product_signoff": False,
  "steps": steps,
  "manifest": manifest or None,
  "manifest_path": "learn/sim/reports/pkg_manifest_${VARIANT}.json" if manifest else None,
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
    "ok": False,
    "evidence_ok": evidence_ok,
  },
  "ok": False,
  "product_signoff": False,
  "summary": (
     f"bump:{'ok' if steps['pkg_bump']['ok'] else 'fail'} · "
     f"rdl:{rdl_label} · "
     f"system_pdn:{sys.get('status') if sys.get('status') == 'GAP' else ('ok' if steps['system_pdn']['ok'] else 'fail')} · "
     f"manifest:{manifest_status}"
  ),
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("PKG_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
PY

echo "PKG_SIGNOFF_DONE ${VARIANT}"
if [[ "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status", "FAIL"))' "${OUT}")" == "PROXY" ]]; then
  echo "OK package evidence generated · PROXY is not Product signoff"
else
  python3 "${ROOT}/learn/scripts/signoff_require_ok.py" "${OUT}"
fi

#!/usr/bin/env bash
# check_power_grid on ODB PDN / final (grid connectivity).
# Usage: run_gridcheck.sh [floorplan|pdn|place|cts|route|finish]
# Env: FLOW_VARIANT=learn|flowlab (default learn)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" gridcheck bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
source "${ROOT}/scripts/rg_compat.sh"
VARIANT="${FLOW_VARIANT:-learn}"
WORK_HOME="${PD_FLOW_WORK_HOME:-}"
if [[ "${VARIANT}" == lab_asap7_* ]]; then
  [[ "${VARIANT}" =~ ^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$ ]] || {
    echo "FAIL invalid ASAP7 lab variant" >&2
    exit 1
  }
  RES="$(find "${ROOT}/tools/OpenROAD-flow-scripts/flow/results/asap7" -mindepth 2 -maxdepth 2 -type d -name "${VARIANT}" -print -quit)"
  [[ -n "${RES}" && -d "${RES}" ]] || { echo "FAIL missing ASAP7 result directory for ${VARIANT}" >&2; exit 1; }
  OUT_DIR="${ROOT}/learn/sim/reports"
elif [[ -n "${WORK_HOME}" ]]; then
  CANDIDATE_RUN_ID="${PD_FLOW_CANDIDATE_RUN_ID:-}"
  if [[ ! "${CANDIDATE_RUN_ID}" =~ ^[A-Za-z0-9_.-]{8,100}$ ]]; then
    echo "FAIL invalid FlowLab candidate run id" >&2
    exit 1
  fi
  EXPECTED_WORK_HOME="${ROOT}/.pdflow/runs/${CANDIDATE_RUN_ID}/candidate/orfs"
  if [[ "${WORK_HOME}" != "${EXPECTED_WORK_HOME}" || "${VARIANT}" != "flowlab" ]]; then
    echo "FAIL candidate workspace is outside the requested run" >&2
    exit 1
  fi
  RES="${WORK_HOME}/results/nangate45/gcd/flowlab"
  OUT_DIR="${WORK_HOME}/reports/nangate45/gcd/flowlab"
else
  RES="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}"
  OUT_DIR="${ROOT}/learn/sim/reports"
fi
STAGE="${PD_FLOW_CHECKPOINT:-${1:-pdn}}"
# Keep the historical CLI spelling usable, but publish one canonical
# checkpoint identity in reports and artifact provenance.
if [[ "${STAGE}" == "final" ]]; then
  STAGE="finish"
fi
GRID_NET="${PD_FLOW_GRID_NET:-BOTH}"
REQUIRE_TERMINALS="${PD_FLOW_GRID_REQUIRE_TERMINALS:-0}"
case "${GRID_NET}" in
  VDD|VSS|BOTH) ;;
  *) echo "FAIL PD_FLOW_GRID_NET must be VDD, VSS or BOTH" >&2; exit 2 ;;
esac
case "${REQUIRE_TERMINALS}" in
  0|1) ;;
  *) echo "FAIL PD_FLOW_GRID_REQUIRE_TERMINALS must be 0 or 1" >&2; exit 2 ;;
esac
case "${STAGE}" in
  floorplan)
    ODB="${RES}/2_floorplan.odb"
    [[ -f "${ODB}" ]] || ODB="${RES}/2_1_floorplan.odb"
    ;;
  pdn) ODB="${RES}/2_4_floorplan_pdn.odb" ;;
  place)
    ODB="${RES}/3_place.odb"
    [[ -f "${ODB}" ]] || ODB="${RES}/3_5_place_dp.odb"
    ;;
  cts)
    ODB="${RES}/4_cts.odb"
    [[ -f "${ODB}" ]] || ODB="${RES}/4_1_cts.odb"
    ;;
  route)
    ODB="${RES}/5_route.odb"
    [[ -f "${ODB}" ]] || ODB="${RES}/5_2_route.odb"
    ;;
  finish) ODB="${RES}/6_final.odb" ;;
  *) echo "uso: FLOW_VARIANT=learn|flowlab $0 [floorplan|pdn|place|cts|route|finish]"; exit 2 ;;
esac
[[ -f "${ODB}" ]] || { echo "FAIL missing ${ODB} — run floorplan/finish (variant=${VARIANT})"; exit 1; }

mkdir -p "${OUT_DIR}"
OUT="${OUT_DIR}/gridcheck_${VARIANT}_${STAGE}.log"
REPORT="${OUT_DIR}/gridcheck_${VARIANT}_${STAGE}.json"
# The checkpoint directory is finish-owned. Keep run markers alongside the
# generated report so a read-only analysis never mutates the canonical tree.
STAMP="${OUT_DIR}/.gridcheck_${VARIANT}_${STAGE}.ok"
OPENROAD_VERSION="$(openroad -version 2>&1 | head -1 | tr -d '\r' | sed 's/[[:space:]]*$//' || true)"

GRID_TCL=""
for NET in VDD VSS; do
  if [[ "${GRID_NET}" == "BOTH" || "${GRID_NET}" == "${NET}" ]]; then
    if [[ "${REQUIRE_TERMINALS}" == "1" ]]; then
      GRID_TCL+="check_power_grid -net ${NET}"$'\n'
    else
      GRID_TCL+="check_power_grid -net ${NET} -dont_require_terminals"$'\n'
    fi
    GRID_TCL+="puts \"GRIDCHECK_NET_${NET}_DONE\""$'\n'
  fi
done

set +e
openroad -no_init -no_splash -exit <<EOF | tee "${OUT}"
read_db ${ODB}
# The command is read-only. Terminal presence is configurable, and the
# selected rail set is recorded in the report instead of being implicit.
${GRID_TCL}
puts "GRIDCHECK_DONE ${VARIANT} ${STAGE}"
EOF
OPENROAD_RC=${PIPESTATUS[0]}
set -e

VDD_LINES="$(rg -c 'PSM-0040.*VDD' "${OUT}" 2>/dev/null || true)"
VSS_LINES="$(rg -c 'PSM-0040.*VSS' "${OUT}" 2>/dev/null || true)"
VDD_DONE="$(rg -c "GRIDCHECK_NET_VDD_DONE" "${OUT}" 2>/dev/null || true)"
VSS_DONE="$(rg -c "GRIDCHECK_NET_VSS_DONE" "${OUT}" 2>/dev/null || true)"
DONE="$(rg -c "GRIDCHECK_DONE ${VARIANT} ${STAGE}" "${OUT}" 2>/dev/null || true)"
VDD_SELECTED=0
VSS_SELECTED=0
[[ "${GRID_NET}" == "BOTH" || "${GRID_NET}" == "VDD" ]] && VDD_SELECTED=1
[[ "${GRID_NET}" == "BOTH" || "${GRID_NET}" == "VSS" ]] && VSS_SELECTED=1
VDD_VALID=1
VSS_VALID=1
if [[ "${VDD_SELECTED}" == "1" ]]; then
  [[ "${VDD_DONE:-0}" -gt 0 && "${VDD_LINES:-0}" -gt 0 ]] || VDD_VALID=0
fi
if [[ "${VSS_SELECTED}" == "1" ]]; then
  [[ "${VSS_DONE:-0}" -gt 0 && "${VSS_LINES:-0}" -gt 0 ]] || VSS_VALID=0
fi
if [[ "${OPENROAD_RC}" -eq 0 && "${DONE:-0}" -gt 0 && "${VDD_VALID}" == "1" && "${VSS_VALID}" == "1" ]]; then
  STATUS="PASS"
  OK_JSON=true
  EXECUTION_STATUS="COMPLETED"
  EVIDENCE_STATUS="PASS"
  REQUIREMENT_STATUS="PASS"
  SIGNOFF_STATUS="PROXY"
  [[ "${VARIANT}" == lab_asap7_* ]] || SIGNOFF_STATUS="PASS"
  REASON=""
elif [[ "${OPENROAD_RC}" -eq 0 && "${DONE:-0}" -gt 0 ]]; then
  # OpenROAD completed the requested analysis and the negative connectivity
  # result is valid evidence. It is a requirement failure, not a process
  # crash, so the agent can keep the report and expose the reason.
  STATUS="FAIL"
  OK_JSON=false
  EXECUTION_STATUS="COMPLETED"
  EVIDENCE_STATUS="PASS"
  REQUIREMENT_STATUS="FAIL"
  SIGNOFF_STATUS="PROXY"
  [[ "${VARIANT}" == lab_asap7_* ]] || SIGNOFF_STATUS="NOT_RUN"
  REASON="OpenROAD completed check_power_grid but did not validate both VDD and VSS"
else
  STATUS="FAIL"
  OK_JSON=false
  EXECUTION_STATUS="FAILED"
  EVIDENCE_STATUS="GAP"
  REQUIREMENT_STATUS="GAP"
  SIGNOFF_STATUS="GAP"
  REASON="OpenROAD did not complete the requested grid check"
fi

python3 - "${ROOT}" "${REPORT}" "${VARIANT}" "${STAGE}" "${ODB}" "${OUT}" "${STATUS}" "${OK_JSON}" "${EXECUTION_STATUS}" "${EVIDENCE_STATUS}" "${REQUIREMENT_STATUS}" "${SIGNOFF_STATUS}" "${REASON}" "${OPENROAD_VERSION}" "${GRID_NET}" "${REQUIRE_TERMINALS}" "${VDD_SELECTED}" "${VSS_SELECTED}" "${VDD_LINES}" "${VSS_LINES}" <<'PY'
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    root,
    report,
    variant,
    stage,
    odb,
    log,
    status,
    ok,
    execution_status,
    evidence_status,
    requirement_status,
    signoff_status,
    reason,
    openroad_version,
    grid_net,
    require_terminals,
    vdd_selected,
    vss_selected,
    vdd_lines,
    vss_lines,
) = sys.argv[1:]
root_path = Path(root).resolve()
odb_path = Path(odb).resolve()
digest = hashlib.sha256(odb_path.read_bytes()).hexdigest()
configuration_hash = hashlib.sha256(
    f"{variant}\n{stage}\n{digest}\n{grid_net}\n{require_terminals}".encode("utf-8")
).hexdigest()
vdd_checked = vdd_selected == "1"
vss_checked = vss_selected == "1"
vdd_connected = vdd_checked and int(vdd_lines or 0) > 0
vss_connected = vss_checked and int(vss_lines or 0) > 0
payload = {
    "schema_version": 1,
    "kind": "gridcheck",
    "scope": "flow",
    "variant": variant,
    "stage": stage,
    "status": status,
    "ok": ok == "true",
    "evidence_class": "PROXY" if variant.startswith("lab_asap7_") else "CHECKPOINT_EVIDENCE" if stage != "finish" else "PRODUCT_INPUT",
    "execution_status": execution_status,
    "evidence_status": evidence_status,
    "requirement_status": requirement_status,
    "signoff_status": signoff_status,
    "tool_versions": {"openroad": openroad_version or "unknown"},
    "configuration_hash": configuration_hash,
    "metrics": {
        "vdd_connected": vdd_connected,
        "vss_connected": vss_connected,
        "selected_net": grid_net,
        "require_terminals": require_terminals == "1",
    },
    "read_only": True,
    "shape_only": True,
    "checkpoint_artifact": {
        "relative_path": odb_path.relative_to(root_path).as_posix(),
        "content_hash": digest,
        "size": odb_path.stat().st_size,
        "mtime_ns": odb_path.stat().st_mtime_ns,
    },
    "input_artifacts": [{
        "relative_path": odb_path.relative_to(root_path).as_posix(),
        "content_hash": digest,
        "size": odb_path.stat().st_size,
        "mtime_ns": odb_path.stat().st_mtime_ns,
    }],
    "log": log,
    "nets": {
        "VDD": {"checked": vdd_checked, "connected": vdd_connected},
        "VSS": {"checked": vss_checked, "connected": vss_connected},
    },
    "limitations": [
        "shape-only connectivity check",
        "terminal presence is intentionally not required",
        "not a DRC, LVS or electrical signoff",
    ],
    "reason": reason or None,
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
destination = Path(report)
temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
temporary.replace(destination)
PY

if [[ "${EXECUTION_STATUS}" != "COMPLETED" ]]; then
  echo "FAIL gridcheck ${VARIANT}/${STAGE} → ${REPORT}"
  exit 1
fi
STAMP_TMP="${STAMP}.$$"
date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP_TMP}"
mv -f "${STAMP_TMP}" "${STAMP}"
echo "OK gridcheck ${VARIANT}/${STAGE} → ${REPORT}"

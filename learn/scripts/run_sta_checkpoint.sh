#!/usr/bin/env bash
# Stage-aware OpenSTA checkpoint analysis.
#
# This is an evidence job, not a recook and not a Product signoff shortcut.
# It reads the selected checkpoint/netlist and writes one report per stage so
# WNS, TNS, setup violations and provenance cannot silently come from a
# different physical checkpoint.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" sta-checkpoint bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
source "${ROOT}/scripts/rg_compat.sh"

VARIANT="${FLOW_VARIANT:-flowlab}"
STAGE="${PD_FLOW_CHECKPOINT:-${1:-finish}}"
STA_MODE="${STA_MODE:-setup}"
STA_MAX_PATHS="${STA_MAX_PATHS:-100}"
case "${STA_MODE}" in
  setup|hold) ;;
  *) echo "FAIL STA_MODE must be setup or hold" >&2; exit 2 ;;
esac
[[ "${STA_MAX_PATHS}" =~ ^[0-9]+$ && "${STA_MAX_PATHS}" -ge 1 && "${STA_MAX_PATHS}" -le 1000 ]] || {
  echo "FAIL STA_MAX_PATHS must be an integer between 1 and 1000" >&2
  exit 2
}
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
BASE_SDC="${ROOT}/learn/designs/nangate45/gcd-tutorial/constraint.sdc"
WORK_HOME="${PD_FLOW_WORK_HOME:-}"

IS_LAB="false"
DESIGN="gcd"
CORNER="TC"
PRIMARY_VT="RVT"
TIME_UNIT="ns"
TIME_SCALE_TO_NS="1.0"
REQUIREMENTS_PROFILE="nangate45/gcd"
LIB_FILES=()

if [[ "${VARIANT}" == lab_asap7_* ]]; then
  [[ -z "${WORK_HOME}" ]] || {
    echo "FAIL ASAP7 lab STA cannot use a FlowLab candidate workspace" >&2
    exit 1
  }
  IS_LAB="true"
  LAB_META="$(
    PYTHONPATH="${ROOT}/learn${PYTHONPATH:+:${PYTHONPATH}}" \
      python3 - "${VARIANT}" "${ROOT}" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[2]).resolve()
from dse.asap7_lab import nldm_lib_files, safe_result_dir, spec_for_variant

variant = sys.argv[1]
spec = spec_for_variant(variant, root)
result = safe_result_dir(variant, root)
libs = nldm_lib_files(spec.corner, spec.primary_vt, root)
if len(libs) != 5:
    raise SystemExit(
        f"FAIL ASAP7 NLDM liberty set is incomplete for {spec.corner}/{spec.primary_vt}: "
        f"found {len(libs)}, expected 5"
    )
print(spec.nickname)
print(spec.corner)
print(spec.primary_vt)
print(result)
for lib in libs:
    print(lib)
PY
  )" || {
    echo "FAIL unable to resolve native ASAP7 variant ${VARIANT}" >&2
    exit 1
  }
  mapfile -t LAB_META_LINES <<< "${LAB_META}"
  [[ "${#LAB_META_LINES[@]}" -ge 9 ]] || {
    echo "FAIL incomplete ASAP7 variant metadata for ${VARIANT}" >&2
    exit 1
  }
  DESIGN="${LAB_META_LINES[0]}"
  CORNER="${LAB_META_LINES[1]}"
  PRIMARY_VT="${LAB_META_LINES[2]}"
  RES="${LAB_META_LINES[3]}"
  LIB_FILES=("${LAB_META_LINES[@]:4}")
  TIME_UNIT="ps"
  TIME_SCALE_TO_NS="0.001"
  REQUIREMENTS_PROFILE="asap7/gcd"
else
  LIB_FILES=("${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib")
fi

if [[ -n "${WORK_HOME}" ]]; then
  RUN_ID="${PD_FLOW_CANDIDATE_RUN_ID:-}"
  [[ "${RUN_ID}" =~ ^[A-Za-z0-9_.-]{8,100}$ ]] || { echo "FAIL invalid candidate run id" >&2; exit 1; }
  EXPECTED="${ROOT}/.pdflow/runs/${RUN_ID}/candidate/orfs"
  [[ "${WORK_HOME}" == "${EXPECTED}" && "${VARIANT}" == "flowlab" ]] || { echo "FAIL candidate workspace is outside the requested run" >&2; exit 1; }
  RES="${WORK_HOME}/results/nangate45/gcd/flowlab"
  OUT_DIR="${WORK_HOME}/reports/nangate45/gcd/flowlab"
else
  OUT_DIR="${ROOT}/learn/sim/reports"
fi

pick_existing() {
  local candidate
  for candidate in "$@"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

SPEF=""
case "${STAGE}" in
  synth)
    V="$(pick_existing "${RES}/1_synth.v" "${RES}/1_2_yosys.v")" || V="${RES}/1_2_yosys.v"
    ODB="${RES}/1_synth.odb"
    SDC="$(pick_existing "${RES}/1_synth.sdc" "${RES}/1_2_yosys.sdc")" || SDC="${RES}/1_synth.sdc"
    ;;
  floorplan)
    V="$(pick_existing "${RES}/1_synth.v" "${RES}/1_2_yosys.v")" || V="${RES}/1_2_yosys.v"
    ODB="$(pick_existing "${RES}/2_floorplan.odb" "${RES}/2_1_floorplan.odb" "${RES}/2_4_floorplan_pdn.odb")" || ODB="${RES}/2_floorplan.odb"
    SDC="$(pick_existing "${RES}/2_floorplan.sdc" "${RES}/2_1_floorplan.sdc" "${RES}/2_4_floorplan_pdn.sdc")" || SDC="${BASE_SDC}"
    ;;
  pdn)
    V="$(pick_existing "${RES}/1_synth.v" "${RES}/1_2_yosys.v")" || V="${RES}/1_2_yosys.v"
    ODB="$(pick_existing "${RES}/2_4_floorplan_pdn.odb" "${RES}/2_floorplan.odb" "${RES}/2_1_floorplan.odb")" || ODB="${RES}/2_4_floorplan_pdn.odb"
    SDC="$(pick_existing "${RES}/2_4_floorplan_pdn.sdc" "${RES}/2_floorplan.sdc" "${RES}/2_1_floorplan.sdc")" || SDC="${BASE_SDC}"
    ;;
  place)
    V="$(pick_existing "${RES}/1_synth.v" "${RES}/1_2_yosys.v")" || V="${RES}/1_2_yosys.v"
    ODB="$(pick_existing "${RES}/3_place.odb" "${RES}/3_5_place_dp.odb")" || ODB="${RES}/3_place.odb"
    SDC="$(pick_existing "${RES}/3_place.sdc" "${RES}/3_5_place_dp.sdc")" || SDC="${BASE_SDC}"
    ;;
  cts)
    V="$(pick_existing "${RES}/1_synth.v" "${RES}/1_2_yosys.v")" || V="${RES}/1_2_yosys.v"
    ODB="$(pick_existing "${RES}/4_cts.odb" "${RES}/4_1_cts.odb")" || ODB="${RES}/4_cts.odb"
    SDC="$(pick_existing "${RES}/4_cts.sdc" "${RES}/4_1_cts.sdc")" || SDC="${BASE_SDC}"
    ;;
  route)
    V="$(pick_existing "${RES}/1_synth.v" "${RES}/1_2_yosys.v")" || V="${RES}/1_2_yosys.v"
    ODB="$(pick_existing "${RES}/5_2_route.odb" "${RES}/5_route.odb")" || ODB="${RES}/5_route.odb"
    SDC="$(pick_existing "${RES}/5_route.sdc" "${RES}/5_2_route.sdc")" || SDC="${BASE_SDC}"
    SPEF="$(pick_existing "${RES}/5_route.spef" "${RES}/5_2_route.spef")" || SPEF=""
    ;;
  finish)
    V="${RES}/6_final.v"
    ODB="${RES}/6_final.odb"
    SDC="${RES}/6_final.sdc"
    SPEF="${RES}/6_final.spef"
    ;;
  *) echo "FAIL invalid checkpoint: ${STAGE}" >&2; exit 2 ;;
esac

[[ -f "${V}" ]] || { echo "FAIL missing netlist ${V}"; exit 1; }
[[ -f "${ODB}" ]] || { echo "FAIL missing checkpoint ${ODB}"; exit 1; }
for LIB in "${LIB_FILES[@]}"; do
  [[ -f "${LIB}" ]] || { echo "FAIL missing liberty ${LIB}"; exit 1; }
done
[[ -f "${SDC}" ]] || SDC="${BASE_SDC}"
[[ -f "${SDC}" ]] || { echo "FAIL missing SDC ${SDC}"; exit 1; }
[[ -z "${SPEF}" || -f "${SPEF}" ]] || { echo "FAIL missing SPEF ${SPEF}"; exit 1; }

mkdir -p "${OUT_DIR}"
REPORT_KEY="${VARIANT}_${STAGE}"
# Keep setup evidence at the established path for compatibility. Hold uses a
# sidecar so an exploratory mode can never overwrite the setup checkpoint
# report that Product tooling may be consuming.
[[ "${STA_MODE}" == "setup" ]] || REPORT_KEY="${REPORT_KEY}_${STA_MODE}"
LOG="${OUT_DIR}/sta_checkpoint_${REPORT_KEY}.log"
OUT="${OUT_DIR}/sta_checkpoint_${REPORT_KEY}.json"
METRICS="${OUT_DIR}/.sta_checkpoint_${REPORT_KEY}.metrics.json"

STA_VERSION="$(sta -version 2>&1 | head -1 | tr -d '\r' || true)"
STA_COMMANDS=""
for LIB in "${LIB_FILES[@]}"; do
  STA_COMMANDS+="read_liberty {${LIB}}"$'\n'
done
STA_COMMANDS+="read_verilog {${V}}"$'\n'
STA_COMMANDS+="link_design ${DESIGN}"$'\n'
if [[ -n "${SPEF}" ]]; then
  STA_COMMANDS+="read_spef {${SPEF}}"$'\n'
fi
STA_COMMANDS+="read_sdc {${SDC}}"$'\n'

if [[ "${STA_MODE}" == "hold" ]]; then
  STA_WNS_COMMAND="report_wns -min"
  STA_TNS_COMMAND="report_tns -min"
  STA_WORST_COMMAND="report_worst_slack -min"
  STA_CHECKS_COMMAND="report_checks -path_delay min -slack_max 0 -group_path_count ${STA_MAX_PATHS} -format end"
else
  STA_WNS_COMMAND="report_wns"
  STA_TNS_COMMAND="report_tns"
  STA_WORST_COMMAND="report_worst_slack -max"
  STA_CHECKS_COMMAND="report_checks -path_delay max -slack_max 0 -group_path_count ${STA_MAX_PATHS} -format end"
fi

set +e
cd "${FLOW}"
sta -no_init -exit <<EOF 2>&1 | tee "${LOG}"
${STA_COMMANDS}
${STA_WNS_COMMAND}
${STA_TNS_COMMAND}
${STA_WORST_COMMAND}
${STA_CHECKS_COMMAND}
report_clock_min_period
puts "STA_CHECKPOINT_DONE ${VARIANT} ${STAGE}"
EOF
STA_RC=${PIPESTATUS[0]}
set -e

python3 - "${LOG}" "${METRICS}" "${TIME_SCALE_TO_NS}" "${TIME_UNIT}" "${STA_MODE}" "${STA_MAX_PATHS}" <<'PY'
import json
import re
import sys
from pathlib import Path

log = Path(sys.argv[1])
output = Path(sys.argv[2])
scale = float(sys.argv[3])
time_unit = sys.argv[4]
mode = sys.argv[5]
max_paths = int(sys.argv[6])
text = log.read_text(errors="replace")

def first(pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    return float(match.group(1)) if match else None

metrics = {
    "wns_ns": None,
    "tns": None,
    "period_min_ns": None,
    "setup_violations": sum("(VIOLATED)" in line for line in text.splitlines()),
}
for raw_key, pattern, key in (
    ("wns_raw", r"wns\s+(?:max|min)\s+([-+0-9.eE]+)", "wns_ns"),
    ("tns_raw", r"tns\s+(?:max|min)\s+([-+0-9.eE]+)", "tns"),
    ("period_min_raw", r"period_min\s*=\s*([-+0-9.eE]+)", "period_min_ns"),
):
    raw = first(pattern)
    metrics[raw_key] = raw
    if raw is not None:
        metrics[key] = raw * scale
metrics["time_unit"] = time_unit
metrics["time_scale_to_ns"] = scale
metrics["mode"] = mode
metrics["max_paths"] = max_paths
endpoint = None
for line in text.splitlines():
    if "(VIOLATED)" in line:
        fields = line.split()
        endpoint = fields[0] if fields else None
        break
if endpoint:
    metrics["worst_endpoint"] = endpoint
output.write_text(json.dumps({"timing": metrics}, indent=2) + "\n", encoding="utf-8")
print("STA_CHECKPOINT_PARSE", json.dumps(metrics, sort_keys=True))
PY

if [[ "${STA_RC}" -ne 0 ]]; then
  STATUS="FAIL"
  OK_JSON=false
  REASON="OpenSTA exited with code ${STA_RC}"
  EXECUTION_STATUS="FAILED"
  EVIDENCE_STATUS="GAP"
elif [[ "${STA_MODE}" == "hold" ]]; then
  # The current requirements profile defines setup closure only. Hold output
  # is still valid native evidence, but it cannot be presented as a Product
  # timing pass without a declared hold requirement profile.
  STATUS="PROXY"
  OK_JSON=false
  REASON="hold analysis completed; no declared hold signoff profile is configured"
  EXECUTION_STATUS="COMPLETED"
  EVIDENCE_STATUS="PASS"
else
  EVAL="${OUT}.eval"
  set +e
  python3 "${ROOT}/learn/scripts/signoff_eval.py" \
    --pillar timing \
    --profile "${REQUIREMENTS_PROFILE}" \
    --metrics "${METRICS}" \
    --out "${EVAL}" >/dev/null
  EVAL_RC=$?
  set -e
  STATUS="$(python3 - "${EVAL}" "${EVAL_RC}" <<'PY'
import json
import sys
from pathlib import Path
try:
    data = json.loads(Path(sys.argv[1]).read_text())
    print(str(data.get("pillars", {}).get("timing", {}).get("status") or "GAP"))
except (OSError, json.JSONDecodeError):
    print("GAP")
PY
  )"
  [[ "${STATUS}" =~ ^(PASS|FAIL|WARN|PARTIAL|PROXY|GAP|NOT_RUN)$ ]] || STATUS="GAP"
  PARSED="$(python3 - "${METRICS}" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
timing = data.get("timing") if isinstance(data, dict) else {}
required = ("wns_ns", "tns", "period_min_ns", "setup_violations")
print("true" if isinstance(timing, dict) and all(timing.get(key) is not None for key in required) else "false")
PY
)"
  EXECUTION_STATUS="COMPLETED"
  if [[ "${PARSED}" == "true" ]]; then EVIDENCE_STATUS="PASS"; else EVIDENCE_STATUS="GAP"; fi
  if [[ "${STATUS}" == "PASS" ]]; then OK_JSON=true; REASON=""; else OK_JSON=false; REASON="timing requirement is not closed at ${STAGE}"; fi
fi

python3 - "${OUT}" "${METRICS}" "${VARIANT}" "${STAGE}" "${DESIGN}" "${IS_LAB}" "${CORNER}" "${PRIMARY_VT}" "${TIME_UNIT}" "${STA_VERSION}" "${V}" "${ODB}" "${SDC}" "${SPEF}" "${LOG}" "${STATUS}" "${OK_JSON}" "${REASON}" "${EXECUTION_STATUS}" "${EVIDENCE_STATUS}" "${STA_MODE}" "${STA_MAX_PATHS}" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    out,
    metrics_path,
    variant,
    stage,
    design,
    is_lab,
    corner,
    primary_vt,
    time_unit,
    sta_version,
    verilog,
    odb,
    sdc,
    spef,
    log,
    status,
    ok,
    reason,
    execution_status,
    evidence_status,
    mode,
    max_paths,
) = sys.argv[1:]
root = Path.cwd().parents[2]

def ref(raw):
    path = Path(raw).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "content_hash": digest,
        "size": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
    }

metrics = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
input_paths = [verilog, odb, sdc]
if spef:
    input_paths.append(spef)
input_artifacts = [ref(path) for path in input_paths]
configuration_hash = hashlib.sha256(
    "\n".join(
        [
            variant,
            stage,
            design,
            corner,
            primary_vt,
            mode,
            max_paths,
            *[str(path) for path in input_artifacts],
        ]
    ).encode("utf-8")
).hexdigest()
lab = is_lab == "true"
requirement_status = "PROXY" if lab and status == "PASS" else status
signoff_status = "PROXY" if lab else status if stage == "finish" else "NOT_RUN"
payload = {
    "schema_version": 2,
    "kind": "sta_checkpoint",
    "scope": "flow",
    "variant": variant,
    "stage": stage,
    "status": status,
    "ok": ok == "true",
    "evidence_class": "PROXY" if lab else "PRODUCT_INPUT" if stage == "finish" else "CHECKPOINT_EVIDENCE",
    "execution_status": execution_status,
    "evidence_status": evidence_status,
    "requirement_status": requirement_status,
    "signoff_status": signoff_status,
    "engine": "opensta",
    "timing": metrics.get("timing", {}),
    "metrics": {"timing": metrics.get("timing", {})},
    "design": design,
    "corner": corner,
    "vt": primary_vt,
    "mode": mode,
    "max_paths": int(max_paths),
    "tool_versions": {"opensta": sta_version or "unknown"},
    "units": {"time": time_unit, "normalized_time": "ns"},
    "configuration_hash": configuration_hash,
    "checkpoint_artifact": ref(odb),
    "input_artifacts": input_artifacts,
    "log": Path(log).resolve().relative_to(root).as_posix(),
    "reason": reason or None,
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
Path(out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print("STA_CHECKPOINT_JSON", out)
PY

rm -f "${METRICS}" "${OUT}.eval"
echo "STA_CHECKPOINT_DONE ${VARIANT} ${STAGE} status=${STATUS}"
# A valid timing FAIL is an analysis result, not a process crash. The agent
# receives the structured report and exposes its status to the UI.
exit 0

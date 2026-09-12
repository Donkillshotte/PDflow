#!/usr/bin/env bash
# Real vyges-em-ir on the GCD Nangate45 PDNSim mesh (not a reimplementation).
#
# Stack:
#   write_pg_spice (OpenROAD PDNSim BUMPS) → spice_to_pdn.py → vyges-em-ir
#   static: CG + Jacobi  G·V = I
#   dynamic: backward Euler, simultaneous switch at one t50 (engine limit)
#
# Usage: FLOW_VARIANT=flowlab PD_FLOW_CHECKPOINT=finish ./learn/scripts/run_vyges_em_ir.sh
# Env:
#   C_DECAP=50e-15  PEAK_FACTOR=8  SWITCH_T_NS=1.0  SWITCH_DUR_NS=0.08
#   IR_LIMIT_PCT=5.0
#   VYGES_STATIC_ONLY=1   # skip cap/switch
#   VYGES_EM_IR=/path/to/binary
#   PD_FLOW_CHECKPOINT=route|finish
#
# The canonical ORFS result tree is read-only. All intermediate SPICE, PDN,
# engine and stamp files are written under .pdflow/generated (or an explicit
# repository-scoped PD_FLOW_GENERATED_ROOT). The report is a PROXY because a
# qualified foundry EM current-density limit is not part of this open flow.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" vyges-em-ir bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
source "${ROOT}/scripts/rg_compat.sh"
export PYTHONPATH="/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
source "${ROOT}/learn/lib/power_vcd.sh"
VARIANT="${FLOW_VARIANT:-flowlab}"
CHECKPOINT="${PD_FLOW_CHECKPOINT:-finish}"
C_DECAP="${C_DECAP:-50e-15}"
PEAK_FACTOR="${PEAK_FACTOR:-8}"
SWITCH_T_NS="${SWITCH_T_NS:-1.0}"
SWITCH_DUR_NS="${SWITCH_DUR_NS:-0.08}"
IR_LIMIT_PCT="${IR_LIMIT_PCT:-5.0}"
PKG_R="${PKG_R:-0.05}"

if [[ ! "${VARIANT}" =~ ^[A-Za-z0-9_.-]{1,80}$ ]]; then
  echo "REFUSED: invalid Nangate45 variant" >&2
  exit 2
fi
# The adapter is a Nangate45/OpenROAD PDNSim adapter, not a FlowLab-only
# adapter. Allow isolated E2E variants as well, while keeping ASAP7/Lab
# profiles on their own engine and schema. Candidate runs remain protected by
# the explicit work-home checks below.
if [[ "${VARIANT}" == asap7 || "${VARIANT}" == asap7-* ]]; then
  echo "REFUSED: use the ASAP7 chip-PDN adapter for Lab IR evidence" >&2
  exit 2
fi
case "${CHECKPOINT}" in
  route|finish) ;;
  *)
    echo "REFUSED: power-grid EM is defined only for route and finish checkpoints (got ${CHECKPOINT})" >&2
    exit 2
    ;;
esac

FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ODB_NAME="6_final.odb"
if [[ "${CHECKPOINT}" == "route" ]]; then
  ODB_NAME="5_2_route.odb"
fi
ODB="${RES}/${ODB_NAME}"
SDC="${PD_FLOW_SDC_FILE:-${ROOT}/learn/designs/nangate45/gcd-tutorial/constraint.sdc}"
WORK_HOME="${PD_FLOW_WORK_HOME:-}"
if [[ -n "${WORK_HOME}" ]]; then
  CANDIDATE_RUN_ID="${PD_FLOW_CANDIDATE_RUN_ID:-}"
  [[ "${CANDIDATE_RUN_ID}" =~ ^[A-Za-z0-9_.-]{8,100}$ ]] || {
    echo "FAIL invalid FlowLab candidate run id" >&2
    exit 1
  }
  EXPECTED_WORK_HOME="${ROOT}/.pdflow/runs/${CANDIDATE_RUN_ID}/candidate/orfs"
  if [[ "${WORK_HOME}" != "${EXPECTED_WORK_HOME}" || "${VARIANT}" != "flowlab" ]]; then
    echo "FAIL candidate workspace is outside the requested run" >&2
    exit 1
  fi
  RES="${WORK_HOME}/results/nangate45/gcd/flowlab"
  OUT_DIR="${WORK_HOME}/reports/nangate45/gcd/flowlab"
  GENERATED_DEFAULT="${WORK_HOME}/generated/power_grid_em/${CHECKPOINT}"
else
  GENERATED_DEFAULT="${ROOT}/.pdflow/generated/${VARIANT}/${CHECKPOINT}/power_grid_em"
  OUT_DIR="${ROOT}/learn/sim/reports"
fi
GENERATED_ROOT="${PD_FLOW_GENERATED_ROOT:-${GENERATED_DEFAULT}}"
GENERATED_ROOT="$(realpath -m -- "${GENERATED_ROOT}")"
case "${GENERATED_ROOT}" in
  "${ROOT}/.pdflow/"*) ;;
  *)
    echo "REFUSED: PD_FLOW_GENERATED_ROOT must stay below ${ROOT}/.pdflow" >&2
    exit 2
    ;;
esac
WORK="${GENERATED_ROOT}/vyges"
SPICE="${WORK}/pg_vdd_bumps.sp"
REPORT_KEY="${VARIANT}"
if [[ "${CHECKPOINT}" != "finish" ]]; then
  REPORT_KEY="${VARIANT}_${CHECKPOINT}"
fi
JSON="${OUT_DIR}/vyges_em_ir_${REPORT_KEY}.json"
ENGINE_JSON="${WORK}/vyges_engine.json"
LOG="${OUT_DIR}/vyges_em_ir_${REPORT_KEY}.log"
STAMP="${GENERATED_ROOT}/.vyges_em_ir_${VARIANT}_${CHECKPOINT}.ok"

[[ -f "${ODB}" ]] || { echo "GAP missing ${ODB} — run ${CHECKPOINT} first (variant=${VARIANT})"; exit 1; }

BIN="$("${ROOT}/learn/scripts/ensure_vyges_em_ir.sh")"
[[ -x "${BIN}" ]] || { echo "FAIL vyges-em-ir not executable: ${BIN}"; exit 1; }
VYGES_VERSION="$("${BIN}" -V 2>&1 | head -1 | sed 's/[[:space:]]*$//' || true)"
OPENROAD_VERSION="$(openroad -version 2>&1 | head -1 | sed 's/[[:space:]]*$//' || true)"

mkdir -p "${OUT_DIR}" "${WORK}"
: > "${LOG}"
{
  echo "=== VYGES-EM-IR ${VARIANT} ${CHECKPOINT} ==="
  "${BIN}" -V || true
} | tee -a "${LOG}"

echo "=== write_pg_spice (fresh selected checkpoint export) ===" | tee -a "${LOG}"
[[ -f "${LIB}" && -f "${SDC}" ]] || { echo "FAIL missing liberty/SDC"; exit 1; }
ACTIVITY_TCL="$(power_activity_tcl "${ROOT}")"
cd "${FLOW}"
openroad -no_init -no_splash -exit <<EOF | tee -a "${LOG}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
${ACTIVITY_TCL}
report_power
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 -bump_size 70 -bump_interval 3 -external_resistance ${PKG_R}
analyze_power_grid -net VDD -source_type BUMPS
write_pg_spice -net VDD -source_type BUMPS ${SPICE}
puts "VYGES_SPICE_EXPORT_DONE"
EOF
rg -q 'VYGES_SPICE_EXPORT_DONE' "${LOG}"
[[ -f "${SPICE}" ]] || { echo "FAIL missing ${SPICE}"; exit 1; }

DYN_FLAG=(--dynamic)
if [[ "${VYGES_STATIC_ONLY:-0}" == "1" ]]; then
  DYN_FLAG=()
fi

echo "=== spice_to_pdn.py ===" | tee -a "${LOG}"
python3 "${ROOT}/learn/scripts/spice_to_pdn.py" \
  --spice "${SPICE}" \
  --out-dir "${WORK}" \
  --design "gcd_${VARIANT}" \
  --ir-limit-pct "${IR_LIMIT_PCT}" \
  --c-decap "${C_DECAP}" \
  --peak-factor "${PEAK_FACTOR}" \
  --switch-t-ns "${SWITCH_T_NS}" \
  --switch-dur-ns "${SWITCH_DUR_NS}" \
  "${DYN_FLAG[@]}" \
  2>&1 | tee -a "${LOG}"

JOB="${WORK}/gcd_${VARIANT}.emir"
[[ -f "${JOB}" ]] || { echo "FAIL missing job ${JOB}"; exit 1; }

echo "=== vyges-em-ir check ===" | tee -a "${LOG}"
"${BIN}" check "${JOB}" 2>&1 | tee -a "${LOG}"

echo "=== vyges-em-ir run --json ===" | tee -a "${LOG}"
# Engine JSON events go to stderr; --json payload to stdout and -o.
set +e
"${BIN}" run "${JOB}" --json -o "${ENGINE_JSON}" >"${WORK}/stdout.json" 2>"${WORK}/events.ndjson"
rc=$?
set -e
cat "${WORK}/events.ndjson" | tee -a "${LOG}" >/dev/null
# Keep a short human tail in the log
tail -5 "${WORK}/events.ndjson" | tee -a "${LOG}" || true
if [[ "${rc}" -ne 0 ]]; then
  echo "FAIL vyges-em-ir exit ${rc}" | tee -a "${LOG}"
  exit "${rc}"
fi
[[ -f "${ENGINE_JSON}" ]] || { echo "FAIL missing ${ENGINE_JSON}"; exit 1; }

python3 - <<PY | tee -a "${LOG}"
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

root = Path(${ROOT@Q})
variant = ${VARIANT@Q}
checkpoint = ${CHECKPOINT@Q}
engine_path = Path(${ENGINE_JSON@Q})
adapter_path = Path(${WORK@Q}) / f"gcd_{variant}.adapter.json"
out = Path(${JSON@Q})
bin_path = ${BIN@Q}
bin_version = ${VYGES_VERSION@Q}
openroad_version = ${OPENROAD_VERSION@Q}
spice = ${SPICE@Q}
job = ${JOB@Q}
odb = Path(${ODB@Q})

def artifact_ref(path: Path, kind: str) -> dict:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "kind": kind,
        "relative_path": path.relative_to(root).as_posix(),
        "content_hash": digest.hexdigest(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }

raw = json.loads(engine_path.read_text())
adapter = json.loads(adapter_path.read_text()) if adapter_path.exists() else {}

w = raw.get("worst_ir") or {}
d = raw.get("dynamic") if isinstance(raw.get("dynamic"), dict) else None
parts = [
    f"static IR {float(w.get('drop') or 0)*1e3:.3f} mV ({float(w.get('drop_pct') or 0):.3f}%)"
]
if d:
    parts.append(
        f"dynamic droop {float(d.get('drop') or 0)*1e3:.3f} mV ({float(d.get('drop_pct') or 0):.3f}%)"
        + (f" @ {d.get('time_ns')} ns" if d.get("time_ns") is not None else "")
    )
parts.append(f"nodes {raw.get('nodes')}")
em_checked = int(raw.get("em_checked") or 0)
parts.append(f"em_checked {em_checked} (no foundry emlimit)")
if raw.get("ir_met") is False:
    parts.append("ir_met false (educational 5% bound, not tapeout)")
summary = " · ".join(parts)

odb_ref = artifact_ref(odb, "odb")
spice_ref = artifact_ref(Path(spice), "spice")
input_refs = [odb_ref, spice_ref]
config = {
    "variant": variant,
    "checkpoint": checkpoint,
    "c_decap_f": ${C_DECAP@Q},
    "peak_factor": ${PEAK_FACTOR@Q},
    "switch_t_ns": ${SWITCH_T_NS@Q},
    "switch_dur_ns": ${SWITCH_DUR_NS@Q},
    "ir_limit_pct": ${IR_LIMIT_PCT@Q},
    "package_resistance_ohm": ${PKG_R@Q},
    "odb_hash": odb_ref["content_hash"],
    "spice_hash": spice_ref["content_hash"],
}
configuration_hash = hashlib.sha256(
    json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
ir_status = "PASS" if raw.get("ir_met") is True else "FAIL"
em_checked = int(raw.get("em_checked") or 0)
em_status = "PASS" if em_checked > 0 else "GAP"
limitations = [
    "No qualified foundry current-density limit is configured; EM cannot receive PASS.",
    "The engine reports EM coverage as zero for this open mesh; IR is an educational bound only.",
    "The dynamic result is a simultaneous-switch upper bound, not a RedHawk signoff substitute.",
]

payload = {
    "schema_version": 2,
    "status": "PROXY",
    "ok": False,
    "kind": "vyges_em_ir",
    "check_id": "power_grid_em",
    "scope": "flow",
    "evidence_class": "PROXY",
    "execution_status": "COMPLETED",
    "evidence_status": "PASS",
    "requirement_status": "GAP",
    "signoff_status": "PROXY",
    "product_signoff": False,
    "product_win": False,
    "engine": "vyges-em-ir",
    "license": "Apache-2.0",
    "upstream": "https://github.com/vyges-tools/em-ir",
    "version": bin_version or "unknown",
    "binary": bin_path,
    "tool_versions": {
        "openroad": openroad_version or "unknown",
        "vyges-em-ir": bin_version or "unknown",
    },
    "variant": variant,
    "checkpoint": checkpoint,
    "checkpoint_artifact": odb_ref,
    "input_artifacts": input_refs,
    "configuration_hash": configuration_hash,
    "spice": spice,
    "job": job,
    "pdn": str(Path(${WORK@Q}) / f"gcd_{variant}.pdn"),
    "engine_json": str(engine_path),
    "adapter": adapter,
    "vyges": raw,
    "requirements": {
        "ir_bound": {"status": ir_status, "limit_pct": ${IR_LIMIT_PCT@Q}},
        "power_grid_em": {
            "status": em_status,
            "em_checked": em_checked,
            "reason": "No qualified foundry current-density limit is configured.",
        },
    },
    "metrics": {
        "static_ir_v": w.get("drop"),
        "static_ir_pct": w.get("drop_pct"),
        "dynamic_droop_v": d.get("drop") if d else None,
        "dynamic_droop_pct": d.get("drop_pct") if d else None,
        "em_checked": em_checked,
        "nodes": raw.get("nodes"),
    },
    "limits": {
        "simultaneous_switch": True,
        "timestep_not_user_set": True,
        "no_waveform_export": True,
        "not_tapeout_signoff": True,
        "pads_are_ideal_vdd": True,
        "note": "Dynamic IR is a worst-case simultaneous-switch upper bound. Not correlated as a RedHawk drop-in. Static IR uses the same write_pg_spice mesh as pdn_transient.py.",
    },
    "limits_met": False,
    "limitations": limitations,
    "reason": "PROXY evidence only: IR bound is educational and qualified power-grid EM limits are unavailable.",
    "summary": summary,
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
out.parent.mkdir(parents=True, exist_ok=True)
temporary = out.with_name(f".{out.name}.{os.getpid()}.tmp")
temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
os.replace(temporary, out)
print("VYGES_EM_IR_DONE", variant)
print("SUMMARY", summary)
print("report →", out)
PY

date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
echo "OK vyges-em-ir ${VARIANT} ${CHECKPOINT} · proxy evidence (not Product signoff)"
echo "  log:    ${LOG}"
echo "  report: ${JSON}"
echo "  job:    ${JOB}"

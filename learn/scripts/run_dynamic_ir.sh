#!/usr/bin/env bash
# Dynamic IR engine on the GCD write_pg_spice mesh.
# Per-ITerm PWL + live A LU + B SA-AMG + C Krylov MOR + D RAS Schwarz.
# Extract = SPICE + tech LEF (EM J); SPEF PG *D_NET *CAP is stamped by name-join
# (GCD OpenRCX has no VDD — GAP; signal nets are never mapped).
# Grover on-die L is estimated always; descriptor TRAN is ON_DIE_L=1 (not AMG).
# Dual-rail VSS: write_pg_spice -net VSS independently of VDD; pair by Sink-for
# inst (not RTL). VSS TRAN is an independent live rail result.
# Rail-to-rail C is opt-in: instance-pin C_rr (RAIL_C=1) and/or overlapping-strap
# Cox (RAIL_C_GEOM=1) — not the GCD default.
# Electrothermal: default ON reports one-shot R(T) Solver A TRAN (not reference).
#   ELECTROTHERMAL=0 skips that TRAN; N1 restamp still reported.
# Activity = OpenSTA arrival t50 (clock) + VCD/SAIF name-join
# (gate VCD from gate_sim joins; RTL tb_gcd stays GAP).
# SAIF idle-zeros TC=0 pulses; does not invent t50 or rescale I_avg.
# Path STA delay from OpenSTA report_checks (NLDM typical-V × (Vdd/V)^α).
# Ranking of extra I(t) stays Solver A (synthetic). vyges-em-ir is bootstrap.
#
# Usage: FLOW_VARIANT=flowlab ./learn/scripts/run_dynamic_ir.sh
# Env:
#   DYNAMIC_IR_MODE=clock|spatial|simultaneous
#   PEAK_FACTOR=8  C_DECAP=50e-15  PKG_R=0.05  PKG_L=2e-10
#   PERIOD_NS=0.46  DUR_NS=0.08  DT_PS=10
#   DYNAMIC_IR_ADAPTIVE=1  also run adaptive-Δt BE (different L discretization)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" dynamic-ir bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
source "${ROOT}/scripts/rg_compat.sh"
source "${ROOT}/learn/lib/power_vcd.sh"
source "${ROOT}/learn/lib/openroad_python.sh"
source "${ROOT}/scripts/lib/heavy_analysis.sh"
export PYTHONPATH="/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"

VARIANT="${FLOW_VARIANT:-flowlab}"
STAGE="${PD_FLOW_CHECKPOINT:-finish}"
MODE="${DYNAMIC_IR_MODE:-clock}"
PEAK_FACTOR="${PEAK_FACTOR:-8}"
C_DECAP="${C_DECAP:-50e-15}"
PKG_R="${PKG_R:-0.05}"
PKG_L="${PKG_L:-2e-10}"
PERIOD_NS="${PERIOD_NS:-0.46}"
DUR_NS="${DUR_NS:-0.08}"
T50_NS="${T50_NS:-0.12}"
DT_PS="${DT_PS:-10}"

case "${STAGE}" in
  place|cts|route|finish) ;;
  *) echo "REFUSED: dynamic IR is defined for place, cts, route and finish checkpoints (got ${STAGE})" >&2; exit 2 ;;
esac

FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
LEF="${FLOW}/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef"
SDC="${PD_FLOW_SDC_FILE:-${ROOT}/learn/designs/nangate45/gcd-tutorial/constraint.sdc}"
WORK_HOME="${PD_FLOW_WORK_HOME:-}"
if [[ -n "${WORK_HOME}" ]]; then
  CANDIDATE_RUN_ID="${PD_FLOW_CANDIDATE_RUN_ID:-}"
  [[ "${CANDIDATE_RUN_ID}" =~ ^[A-Za-z0-9_.-]{8,100}$ ]] || {
    echo "FAIL invalid FlowLab candidate run id" >&2
    exit 1
  }
  EXPECTED_WORK_HOME="${ROOT}/.pdflow/runs/${CANDIDATE_RUN_ID}/candidate/orfs"
  [[ "${WORK_HOME}" == "${EXPECTED_WORK_HOME}" && "${VARIANT}" == "flowlab" ]] || {
    echo "FAIL candidate workspace is outside the requested run" >&2
    exit 1
  }
  RES="${WORK_HOME}/results/nangate45/gcd/flowlab"
  OUT_DIR="${WORK_HOME}/reports/nangate45/gcd/flowlab"
  GENERATED_DEFAULT="${WORK_HOME}/generated/dynamic_ir/${STAGE}"
else
  OUT_DIR="${ROOT}/learn/sim/reports"
  GENERATED_DEFAULT="${ROOT}/.pdflow/generated/${VARIANT}/${STAGE}/dynamic_ir"
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

case "${STAGE}" in
  place)
    ODB="$(pick_existing "${RES}/3_place.odb" "${RES}/3_5_place_dp.odb")" || ODB="${RES}/3_place.odb"
    V="$(pick_existing "${RES}/1_synth.v" "${RES}/1_2_yosys.v")" || V="${RES}/1_2_yosys.v"
    SPEF=""
    ;;
  cts)
    ODB="$(pick_existing "${RES}/4_cts.odb" "${RES}/4_1_cts.odb")" || ODB="${RES}/4_cts.odb"
    V="$(pick_existing "${RES}/1_synth.v" "${RES}/1_2_yosys.v")" || V="${RES}/1_2_yosys.v"
    SPEF=""
    ;;
  route)
    ODB="$(pick_existing "${RES}/5_2_route.odb" "${RES}/5_route.odb")" || ODB="${RES}/5_2_route.odb"
    V="$(pick_existing "${RES}/1_synth.v" "${RES}/1_2_yosys.v")" || V="${RES}/1_2_yosys.v"
    SPEF="$(pick_existing "${RES}/5_route.spef" "${RES}/5_2_route.spef")" || SPEF=""
    ;;
  finish)
    ODB="${RES}/6_final.odb"
    V="${RES}/6_final.v"
    SPEF="${RES}/6_final.spef"
    ;;
esac

GENERATED_ROOT="${PD_FLOW_GENERATED_ROOT:-${GENERATED_DEFAULT}}"
GENERATED_ROOT="$(realpath -m -- "${GENERATED_ROOT}")"
case "${GENERATED_ROOT}" in
  "${ROOT}/.pdflow/"*|"${WORK_HOME}/generated/"*) ;;
  *) echo "REFUSED: PD_FLOW_GENERATED_ROOT must remain repository/candidate scoped" >&2; exit 2 ;;
esac
REPORT_KEY="${VARIANT}"
[[ "${STAGE}" == "finish" ]] || REPORT_KEY="${VARIANT}_${STAGE}"
WORK="${GENERATED_ROOT}/mesh"
SPICE="${WORK}/pg_vdd_bumps.sp"
SPICE_VSS="${WORK}/pg_vss_bumps.sp"
INSTS="${WORK}/inst_power_map.json"
JSON="${OUT_DIR}/dynamic_ir_${REPORT_KEY}_direct.json"
LOG="${OUT_DIR}/dynamic_ir_${REPORT_KEY}_direct.log"
STA_JSON="${WORK}/sta_arrivals.json"
VCD=""
if VCD="$(power_vcd_path "${ROOT}")"; then
  :
else
  VCD=""
fi
STAMP="${GENERATED_ROOT}/.dynamic_ir_${VARIANT}_${STAGE}.ok"

[[ -f "${ODB}" ]] || { echo "FAIL missing ${ODB} — run ${STAGE} first (variant=${VARIANT})"; exit 1; }
[[ -f "${V}" ]] || { echo "FAIL missing netlist ${V}"; exit 1; }
mkdir -p "${OUT_DIR}" "${WORK}"
: > "${LOG}"

if [[ ! -f "${ROOT}/engine/build/libdpn.so" ]]; then
  echo "=== build libdpn ===" | tee -a "${LOG}"
  "${ROOT}/learn/scripts/build_dpn_engine.sh" 2>&1 | tee -a "${LOG}"
fi

echo "=== export inst_power_map ===" | tee -a "${LOG}"
openroad_odb_python \
  "${ROOT}/learn/scripts/export_odb_inst_power.py" "${ODB}" "${INSTS}" \
  2>&1 | tee -a "${LOG}"

write_pg_net() {
  local net="$1"
  local out="$2"
  echo "=== write_pg_spice -net ${net} ===" | tee -a "${LOG}"
  local ACTIVITY_TCL
  ACTIVITY_TCL="$(power_activity_tcl "${ROOT}")"
  cd "${FLOW}"
  openroad -no_init -no_splash -exit <<EOF | tee -a "${LOG}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
${ACTIVITY_TCL}
report_power
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 -bump_size 70 -bump_interval 3 -external_resistance ${PKG_R}
analyze_power_grid -net ${net} -source_type BUMPS
write_pg_spice -net ${net} -source_type BUMPS ${out}
puts "DYNAMIC_IR_SPICE_${net}_DONE"
EOF
  rg -q "DYNAMIC_IR_SPICE_${net}_DONE" "${LOG}"
}

write_pg_net VDD "${SPICE}"
[[ -f "${SPICE}" ]] || { echo "FAIL missing ${SPICE}"; exit 1; }

write_pg_net VSS "${SPICE_VSS}"

n_r="$(grep -cE '^[Rr]' "${SPICE}" || true)"
n_r="${n_r:-0}"
if [[ "${n_r}" -gt 20000 ]]; then
  require_heavy_analysis "dynamic IR spice n_r=${n_r} > 20000" | tee -a "${LOG}" || exit 2
fi

if ! command -v sta >/dev/null 2>&1; then
  echo "FAIL OpenSTA (sta) not in PATH — needed for arrival t50" | tee -a "${LOG}"
  exit 1
fi
echo "=== OpenSTA report_arrival → ${STA_JSON} ===" | tee -a "${LOG}"
unset STA_SPEF
if [[ -n "${SPEF}" && -f "${SPEF}" ]]; then
  export STA_SPEF="${SPEF}"
fi
STA_LIB="${LIB}" STA_V="${V}" STA_SDC="${SDC}" STA_OUT="${STA_JSON}" FLOW_VARIANT="${VARIANT}" \
  python3 "${ROOT}/learn/scripts/export_sta_arrivals.py" 2>&1 | tee -a "${LOG}"
[[ -f "${STA_JSON}" ]] || { echo "FAIL missing ${STA_JSON}"; exit 1; }
rg -q 'STA_ARRIVALS_JSON' "${LOG}"

echo "=== pdn_dynamic.py mode=${MODE} ===" | tee -a "${LOG}"
ADAPT=()
if [[ "${DYNAMIC_IR_ADAPTIVE:-}" == "1" ]]; then
  ADAPT=(--adaptive)
fi
EXTRA=()
if [[ -f "${LEF}" ]]; then
  EXTRA+=(--lef "${LEF}")
fi
if [[ -f "${SPEF}" ]]; then
  EXTRA+=(--spef "${SPEF}")
fi
EXTRA+=(--sta "${STA_JSON}")
if [[ -n "${VCD}" && -f "${VCD}" ]]; then
  EXTRA+=(--vcd "${VCD}")
fi
if [[ "${ON_DIE_L:-}" == "1" ]]; then
  EXTRA+=(--on-die-l)
fi
if [[ "${RAIL_C:-}" == "1" ]]; then
  EXTRA+=(--rail-c)
  if [[ -n "${RAIL_C_F:-}" ]]; then
    EXTRA+=(--rail-c-f "${RAIL_C_F}")
  fi
fi
if [[ "${RAIL_C_GEOM:-}" == "1" ]]; then
  EXTRA+=(--rail-c-geom)
fi
if [[ "${ELECTROTHERMAL:-1}" == "0" ]]; then
  EXTRA+=(--no-electrothermal)
fi
if [[ -f "${SPICE_VSS}" ]]; then
  EXTRA+=(--spice-vss "${SPICE_VSS}")
fi
if [[ "${SKIP_NGSPICE:-0}" == "1" || ! "$(command -v ngspice 2>/dev/null || true)" ]]; then
  # Keep the report explicit about the unavailable external engine. Never
  # substitute an output from a different invocation.
  EXTRA+=(--skip-ngspice)
fi
python3 "${ROOT}/learn/scripts/pdn_dynamic.py" \
  --spice "${SPICE}" \
  --insts "${INSTS}" \
  --out "${JSON}" \
  --mode "${MODE}" \
  --peak-factor "${PEAK_FACTOR}" \
  --period-ns "${PERIOD_NS}" \
  --dur-ns "${DUR_NS}" \
  --t50-ns "${T50_NS}" \
  --pkg-r "${PKG_R}" \
  --pkg-l "${PKG_L}" \
  --c-decap "${C_DECAP}" \
  --dt-ps "${DT_PS}" \
  --liberty "${LIB}" \
  "${EXTRA[@]}" \
  "${ADAPT[@]}" \
  2>&1 | tee -a "${LOG}"

rg -q 'DYNAMIC_IR_DONE' "${LOG}"
[[ -f "${JSON}" ]] || { echo "FAIL missing ${JSON}"; exit 1; }
python3 - "${ROOT}" "${JSON}" "${ODB}" "${SPICE}" "${V}" "${SDC}" "${SPEF}" "${STA_JSON}" "${INSTS}" "${VARIANT}" "${STAGE}" "${MODE}" "${PERIOD_NS}" "${DUR_NS}" "${DT_PS}" "${PKG_R}" "${PKG_L}" "${C_DECAP}" "${PEAK_FACTOR}" <<'PY' | tee -a "${LOG}"
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    root,
    report_raw,
    odb_raw,
    spice_raw,
    verilog_raw,
    sdc_raw,
    spef_raw,
    sta_raw,
    insts_raw,
    variant,
    stage,
    mode,
    period_ns,
    duration_ns,
    timestep_ps,
    pkg_r,
    pkg_l,
    c_decap,
    peak_factor,
) = sys.argv[1:]
root_path = Path(root).resolve()
report_file = Path(report_raw).resolve()

def ref(raw: str) -> dict:
    path = Path(raw).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "relative_path": path.relative_to(root_path).as_posix(),
        "content_hash": digest,
        "size": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
    }

input_refs = [ref(item) for item in [odb_raw, spice_raw, verilog_raw, sdc_raw, sta_raw, insts_raw]]
if spef_raw:
    input_refs.append(ref(spef_raw))
output_refs = []
for candidate in (
    report_file,
    Path(str(report_file.with_suffix("")) + ".wave.csv"),
    Path(str(report_file.with_suffix("")) + ".map.csv"),
    Path(str(report_file.with_suffix("")) + ".svg"),
):
    if candidate.is_file():
        output_refs.append(ref(str(candidate)))
configuration_hash = hashlib.sha256(
    "\n".join(
        [
            variant,
            stage,
            mode,
            period_ns,
            duration_ns,
            timestep_ps,
            pkg_r,
            pkg_l,
            c_decap,
            peak_factor,
            *[item["content_hash"] for item in input_refs],
        ]
    ).encode("utf-8")
).hexdigest()
data = json.loads(report_file.read_text(encoding="utf-8"))
data.update(
    {
        "schema_version": 2,
        "status": "PROXY",
        "ok": False,
        "scope": "flow",
        "variant": variant,
        "stage": stage,
        "checkpoint_id": stage,
        "evidence_class": "PRODUCT_INPUT" if stage == "finish" else "CHECKPOINT_EVIDENCE",
        "execution_status": "COMPLETED",
        "evidence_status": "PASS",
        "requirement_status": "GAP",
        "signoff_status": "PROXY",
        "checkpoint_artifact": input_refs[0],
        "input_artifacts": input_refs,
        "input_artifact_refs": input_refs,
        "output_artifacts": output_refs,
        "configuration_hash": configuration_hash,
        "product_signoff": False,
        "limitations": [
            "open-chip dynamic IR evidence; no qualified Product power limit is configured",
            "activity and current models are declared in the report and are not a foundry power signoff",
            "the report is valid same-run evidence but cannot close Product signoff",
        ],
        "reason": "dynamic IR evidence completed; configure qualified power limits before Product signoff",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
)
temporary = report_file.with_name(f".{report_file.name}.{os.getpid()}.tmp")
temporary.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
os.replace(temporary, report_file)
print("DYNAMIC_IR_REPORT", report_file)
PY

STAMP_TMP="${STAMP}.$$"
date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP_TMP}"
mv -f "${STAMP_TMP}" "${STAMP}"
echo "OK dynamic IR evidence ${VARIANT}/${STAGE} mode=${MODE} · PROXY (not Product signoff)"
echo "  report: ${JSON}"
echo "  svg:    ${JSON%.json}.svg"

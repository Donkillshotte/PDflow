#!/usr/bin/env bash
# Chip PDN IR — on-die static (OpenROAD PDNSim) + transient on write_pg_spice.
#
# This is NOT System PDN (VRM/board/package). For hierarchical System PDN:
#   learn/scripts/run_system_pdn.sh
#
# Stack:
#   1. OpenROAD psm: set_pdnsim_source_settings + analyze_power_grid
#      + write_pg_spice  (static IR, package R proxy, bump/strap sources)
#   2. learn/scripts/pdn_transient.py — backward-Euler dynamic IR on that
#      SPICE mesh (VoltSpot-style). Real vyges-em-ir: run_vyges_em_ir.sh
#
# Usage: run_chip_pdn_ir.sh
# Env:
#   FLOW_VARIANT=learn|flowlab
#   PKG_R=0.05          # package series resistance proxy (ohm)
#   PKG_L=2e-10         # package series inductance (H)
#   C_DECAP=50e-15      # decap per load node (F)
#   PEAK_FACTOR=8       # simultaneous-switch peak vs average current
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" chip-pdn-ir bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
source "${ROOT}/scripts/rg_compat.sh"
# shellcheck source=learn/lib/power_vcd.sh
source "${ROOT}/learn/lib/power_vcd.sh"
VARIANT="${FLOW_VARIANT:-flowlab}"
STAGE="${PD_FLOW_CHECKPOINT:-finish}"
case "${STAGE}" in
  place|cts|route|finish) ;;
  *) echo "REFUSED: chip PDN is defined for place, cts, route and finish checkpoints (got ${STAGE})" >&2; exit 2 ;;
esac
ACTIVITY_TCL="$(power_activity_tcl "${ROOT}")"
PKG_R="${PKG_R:-0.05}"
PKG_L="${PKG_L:-2e-10}"
C_DECAP="${C_DECAP:-50e-15}"
PEAK_FACTOR="${PEAK_FACTOR:-8}"

FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ODB="${RES}/6_final.odb"
SDC="${PD_FLOW_SDC_FILE:-${ROOT}/learn/designs/nangate45/gcd-tutorial/constraint.sdc}"

WORK_HOME="${PD_FLOW_WORK_HOME:-}"
if [[ -n "${WORK_HOME}" ]]; then
  RUN_ID="${PD_FLOW_CANDIDATE_RUN_ID:-}"
  [[ "${RUN_ID}" =~ ^[A-Za-z0-9_.-]{8,100}$ ]] || {
    echo "FAIL invalid FlowLab candidate run id" >&2
    exit 1
  }
  EXPECTED_WORK_HOME="${ROOT}/.pdflow/runs/${RUN_ID}/candidate/orfs"
  [[ "${WORK_HOME}" == "${EXPECTED_WORK_HOME}" && "${VARIANT}" == "flowlab" ]] || {
    echo "FAIL candidate workspace is outside the requested run" >&2
    exit 1
  }
  RES="${WORK_HOME}/results/nangate45/gcd/flowlab"
  OUT_DIR="${WORK_HOME}/reports/nangate45/gcd/flowlab"
  GENERATED_DEFAULT="${WORK_HOME}/generated/chip_pdn_ir/${STAGE}"
else
  OUT_DIR="${ROOT}/learn/sim/reports"
  GENERATED_DEFAULT="${ROOT}/.pdflow/generated/${VARIANT}/${STAGE}/chip_pdn_ir"
fi

case "${STAGE}" in
  place)
    ODB="${RES}/3_place.odb"
    [[ -f "${ODB}" ]] || ODB="${RES}/3_5_place_dp.odb"
    ;;
  cts)
    ODB="${RES}/4_cts.odb"
    [[ -f "${ODB}" ]] || ODB="${RES}/4_1_cts.odb"
    ;;
  route)
    ODB="${RES}/5_2_route.odb"
    [[ -f "${ODB}" ]] || ODB="${RES}/5_route.odb"
    ;;
  finish) ODB="${RES}/6_final.odb" ;;
esac

[[ -f "${ODB}" ]] || { echo "FAIL missing ${ODB} — run finish first (variant=${VARIANT})"; exit 1; }
[[ -f "${LIB}" ]] || { echo "FAIL missing liberty"; exit 1; }
[[ -f "${SDC}" ]] || { echo "FAIL missing SDC"; exit 1; }

GENERATED_ROOT="${PD_FLOW_GENERATED_ROOT:-${GENERATED_DEFAULT}}"
GENERATED_ROOT="$(realpath -m -- "${GENERATED_ROOT}")"
case "${GENERATED_ROOT}" in
  "${ROOT}/.pdflow/"*|"${WORK_HOME}/generated/"*) ;;
  *) echo "REFUSED: PD_FLOW_GENERATED_ROOT must remain repository/candidate scoped" >&2; exit 2 ;;
esac
REPORT_KEY="${VARIANT}"
[[ "${STAGE}" == "finish" ]] || REPORT_KEY="${VARIANT}_${STAGE}"
WORK="${GENERATED_ROOT}/mesh"
mkdir -p "${OUT_DIR}" "${WORK}"
LOG="${OUT_DIR}/chip_pdn_ir_${REPORT_KEY}.log"
STAMP="${GENERATED_ROOT}/.chip_pdn_ir_${VARIANT}_${STAGE}.ok"
SPICE_BUMPS="${WORK}/pg_vdd_bumps.sp"
VOLT_BUMPS="${WORK}/ir_bumps.csv"
TRANSIENT_JSON="${OUT_DIR}/pdn_chip_ir_${REPORT_KEY}.json"
# Keep the legacy finish filename for older UI/scripts, but never create a
# second ambiguous report for intermediate checkpoints.
LEGACY_JSON="${OUT_DIR}/pdn_transient_${VARIANT}.json"
TRANSIENT_WAVE="${OUT_DIR}/pdn_chip_ir_${REPORT_KEY}.wave.csv"

cd "${FLOW}"
openroad -no_init -no_splash -exit <<EOF | tee "${LOG}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
${ACTIVITY_TCL}
report_power

# Package-aware static source model (OpenROAD PDNSim) — still chip-centric
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 -bump_size 70 -bump_interval 3 -external_resistance ${PKG_R}

puts "=== STATIC STRAPS ==="
analyze_power_grid -net VDD -source_type STRAPS
analyze_power_grid -net VSS -source_type STRAPS

puts "=== STATIC FULL ==="
analyze_power_grid -net VDD -source_type FULL
analyze_power_grid -net VSS -source_type FULL

puts "=== STATIC BUMPS + voltage map ==="
analyze_power_grid -net VDD -source_type BUMPS -voltage_file ${VOLT_BUMPS}
analyze_power_grid -net VSS -source_type BUMPS

puts "=== EXPORT write_pg_spice (BUMPS) for transient engine ==="
write_pg_spice -net VDD -source_type BUMPS ${SPICE_BUMPS}

puts "CHIP_PDN_STATIC_DONE ${VARIANT}"
EOF

rg -q 'CHIP_PDN_STATIC_DONE' "${LOG}"
rg -q 'Worstcase IR drop' "${LOG}"
[[ -f "${SPICE_BUMPS}" ]] || { echo "FAIL missing spice ${SPICE_BUMPS}"; exit 1; }

echo "=== TRANSIENT IR (pdn_transient.py · on-die mesh) ===" | tee -a "${LOG}"
export PYTHONPATH="/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
python3 "${ROOT}/learn/scripts/pdn_transient.py" \
  --spice "${SPICE_BUMPS}" \
  --out "${TRANSIENT_JSON}" \
  --wave "${TRANSIENT_WAVE}" \
  --mode BUMPS \
  --pkg-r "${PKG_R}" \
  --pkg-l "${PKG_L}" \
  --c-decap "${C_DECAP}" \
  --peak-factor "${PEAK_FACTOR}" \
  2>&1 | tee -a "${LOG}"

rg -q 'PDN_TRANSIENT_DONE' "${LOG}"
[[ -f "${TRANSIENT_JSON}" ]] || { echo "FAIL missing ${TRANSIENT_JSON}"; exit 1; }

python3 - "${ROOT}" "${TRANSIENT_JSON}" "${ODB}" "${SPICE_BUMPS}" "${TRANSIENT_WAVE}" "${VARIANT}" "${STAGE}" "${PKG_R}" "${PKG_L}" "${C_DECAP}" "${PEAK_FACTOR}" <<'PY' | tee -a "${LOG}"
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

root, report_path, odb_raw, spice_raw, wave_raw, variant, stage, pkg_r, pkg_l, c_decap, peak_factor = sys.argv[1:]
root_path = Path(root).resolve()
report_file = Path(report_path).resolve()
odb = Path(odb_raw).resolve()
spice = Path(spice_raw).resolve()
wave = Path(wave_raw).resolve()

def ref(path: Path) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "relative_path": path.relative_to(root_path).as_posix(),
        "content_hash": digest,
        "size": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
    }

data = json.loads(report_file.read_text(encoding="utf-8"))
odb_ref = ref(odb)
spice_ref = ref(spice)
wave_ref = ref(wave) if wave.is_file() else None
configuration_hash = hashlib.sha256(
    "\n".join(
        [
            variant,
            stage,
            str(pkg_r),
            str(pkg_l),
            str(c_decap),
            str(peak_factor),
            odb_ref["content_hash"],
            spice_ref["content_hash"],
        ]
    ).encode("utf-8")
).hexdigest()
data.update(
    {
        "schema_version": 2,
        "status": "PROXY",
        "ok": False,
        "scope": "flow",
        "variant": variant,
        "stage": stage,
        "evidence_class": "PRODUCT_INPUT" if stage == "finish" else "CHECKPOINT_EVIDENCE",
        "execution_status": "COMPLETED",
        "evidence_status": "PASS",
        "requirement_status": "GAP",
        "signoff_status": "PROXY",
        "checkpoint_id": stage,
        "checkpoint_artifact": odb_ref,
        "input_artifacts": [odb_ref, spice_ref],
        "input_artifact_refs": [odb_ref, spice_ref],
        "output_artifacts": [item for item in [wave_ref] if item is not None],
        "configuration_hash": configuration_hash,
        "product_signoff": False,
        "limitations": [
            "open-chip PDN transient evidence; no qualified Product power limit is configured",
            "package R/L are an explicit model, not extracted package signoff data",
            "the report is valid evidence but cannot close Product signoff",
        ],
        "reason": "chip IR evidence completed; configure a qualified power requirement before Product signoff",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
)
temporary = report_file.with_name(f".{report_file.name}.{os.getpid()}.tmp")
temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
os.replace(temporary, report_file)
print("CHIP_PDN_REPORT", report_file)
PY

if [[ "${STAGE}" == "finish" ]]; then
  cp -f "${TRANSIENT_JSON}" "${LEGACY_JSON}"
fi

python3 - <<PY | tee -a "${LOG}"
import json
r=json.load(open("${TRANSIENT_JSON}"))
print("SUMMARY", r["summary"])
print("STATIC_IR_mV", round(r["static"]["worst_ir"]*1e3, 4))
print("TRANSIENT_DROOP_mV", round(r["transient"]["worst_droop"]*1e3, 4))
print("TRANSIENT_DROOP_PCT", round(r["transient"]["worst_droop_pct"], 4))
PY

STAMP_TMP="${STAMP}.$$"
date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP_TMP}"
mv -f "${STAMP_TMP}" "${STAMP}"
echo "CHIP_PDN_IR_DONE ${VARIANT} ${STAGE}" | tee -a "${LOG}"
echo "OK chip PDN IR evidence ${VARIANT}/${STAGE} · PROXY (not Product signoff)"
echo "  static log: ${LOG}"
echo "  spice:      ${SPICE_BUMPS}"
echo "  report:     ${TRANSIENT_JSON}"
echo "  waveform:   ${TRANSIENT_WAVE}"
echo "Note: System PDN (VRM/board/pkg) → ./learn/scripts/run_system_pdn.sh"

#!/usr/bin/env bash
# Real vyges-em-ir on the GCD Nangate45 PDNSim mesh (not a reimplementation).
#
# Stack:
#   write_pg_spice (OpenROAD PDNSim BUMPS) → spice_to_pdn.py → vyges-em-ir
#   static: CG + Jacobi  G·V = I
#   dynamic: backward Euler, simultaneous switch at one t50 (engine limit)
#
# Uso: FLOW_VARIANT=flowlab ./learn/scripts/run_vyges_em_ir.sh
# Env:
#   C_DECAP=50e-15  PEAK_FACTOR=8  SWITCH_T_NS=1.0  SWITCH_DUR_NS=0.08
#   IR_LIMIT_PCT=5.0
#   VYGES_STATIC_ONLY=1   # skip cap/switch
#   VYGES_EM_IR=/path/to/binary
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${ROOT}/learn/lib/power_vcd.sh"
VARIANT="${FLOW_VARIANT:-flowlab}"
C_DECAP="${C_DECAP:-50e-15}"
PEAK_FACTOR="${PEAK_FACTOR:-8}"
SWITCH_T_NS="${SWITCH_T_NS:-1.0}"
SWITCH_DUR_NS="${SWITCH_DUR_NS:-0.08}"
IR_LIMIT_PCT="${IR_LIMIT_PCT:-5.0}"
PKG_R="${PKG_R:-0.05}"

FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ODB="${RES}/6_final.odb"
SDC="${FLOW}/designs/nangate45/gcd-tutorial/constraint.sdc"
SPICE="${RES}/pdn/pg_vdd_bumps.sp"
WORK="${RES}/pdn/vyges"
OUT_DIR="${ROOT}/learn/sim/reports"
JSON="${OUT_DIR}/vyges_em_ir_${VARIANT}.json"
ENGINE_JSON="${WORK}/vyges_engine.json"
LOG="${OUT_DIR}/vyges_em_ir_${VARIANT}.log"
STAMP="${RES}/.vyges_em_ir.ok"

[[ -f "${ODB}" ]] || { echo "FAIL manca ${ODB} — esegui finish (variant=${VARIANT})"; exit 1; }

BIN="$("${ROOT}/learn/scripts/ensure_vyges_em_ir.sh")"
[[ -x "${BIN}" ]] || { echo "FAIL vyges-em-ir non eseguibile: ${BIN}"; exit 1; }

mkdir -p "${OUT_DIR}" "${WORK}" "${RES}/pdn"
: > "${LOG}"
{
  echo "=== VYGES-EM-IR ${VARIANT} ==="
  "${BIN}" -V || true
} | tee -a "${LOG}"

if [[ ! -f "${SPICE}" ]]; then
  echo "=== write_pg_spice (mesh assente) ===" | tee -a "${LOG}"
  [[ -f "${LIB}" && -f "${SDC}" ]] || { echo "FAIL manca liberty/SDC"; exit 1; }
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
fi
[[ -f "${SPICE}" ]] || { echo "FAIL manca ${SPICE}"; exit 1; }

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
[[ -f "${JOB}" ]] || { echo "FAIL manca job ${JOB}"; exit 1; }

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
[[ -f "${ENGINE_JSON}" ]] || { echo "FAIL manca ${ENGINE_JSON}"; exit 1; }

python3 - <<PY | tee -a "${LOG}"
import json, shutil
from pathlib import Path
from datetime import datetime, timezone

root = Path(${ROOT@Q})
variant = ${VARIANT@Q}
engine_path = Path(${ENGINE_JSON@Q})
adapter_path = Path(${WORK@Q}) / f"gcd_{variant}.adapter.json"
out = Path(${JSON@Q})
bin_path = ${BIN@Q}
spice = ${SPICE@Q}
job = ${JOB@Q}

raw = json.loads(engine_path.read_text())
adapter = json.loads(adapter_path.read_text()) if adapter_path.exists() else {}
compare = {}
tran = root / f"learn/sim/reports/pdn_chip_ir_{variant}.json"
if tran.exists():
    t = json.loads(tran.read_text())
    st = t.get("static") or {}
    dyn = t.get("transient") or {}
    w = raw.get("worst_ir") or {}
    d = raw.get("dynamic") or {}
    compare = {
        "pdn_transient_static_ir_v": st.get("worst_ir"),
        "pdn_transient_static_ir_pct": st.get("worst_ir_pct"),
        "pdn_transient_droop_v": dyn.get("worst_droop"),
        "vyges_static_ir_v": w.get("drop"),
        "vyges_static_ir_pct": w.get("drop_pct"),
        "vyges_dynamic_droop_v": d.get("drop") if isinstance(d, dict) else None,
        "vyges_dynamic_droop_pct": d.get("drop_pct") if isinstance(d, dict) else None,
    }
    vs = compare["vyges_static_ir_v"]
    ps = compare["pdn_transient_static_ir_v"]
    if vs and ps and ps > 0:
        compare["static_ir_ratio_vyges_over_pdn_transient"] = vs / ps

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
summary = " · ".join(parts)

payload = {
    "ok": True,
    "kind": "vyges_em_ir",
    "engine": "vyges-em-ir",
    "license": "Apache-2.0",
    "upstream": "https://github.com/vyges-tools/em-ir",
    "version": "0.1.33",
    "binary": bin_path,
    "variant": variant,
    "spice": spice,
    "job": job,
    "pdn": str(Path(${WORK@Q}) / f"gcd_{variant}.pdn"),
    "engine_json": str(engine_path),
    "adapter": adapter,
    "vyges": raw,
    "compare": compare,
    "limits": {
        "simultaneous_switch": True,
        "timestep_not_user_set": True,
        "no_waveform_export": True,
        "not_tapeout_signoff": True,
        "pads_are_ideal_vdd": True,
        "note": "Dynamic IR is a worst-case simultaneous-switch upper bound. Not correlated as a RedHawk drop-in. Static IR uses the same write_pg_spice mesh as pdn_transient.py.",
    },
    "summary": summary,
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2) + "\n")
print("VYGES_EM_IR_DONE", variant)
print("SUMMARY", summary)
print("report →", out)
PY

date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
echo "OK vyges-em-ir ${VARIANT}"
echo "  log:    ${LOG}"
echo "  report: ${JSON}"
echo "  job:    ${JOB}"

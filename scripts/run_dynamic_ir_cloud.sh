#!/usr/bin/env bash
# GCD Dynamic IR, one extra solver per invocation, 8 GiB cap.
# Solver A (DirectLU) always runs as the teacher. SOLVER selects B/D/C.
# Does not run AES. Does not restamp gold. Skips VSS, electrothermal, extra I(t).
#
#   SOLVER=direct|amg|ras|krylov ./scripts/run_dynamic_ir_cloud.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/scripts/lib/heavy_analysis.sh"
source "${ROOT}/learn/lib/power_vcd.sh"
VARIANT="${FLOW_VARIANT:-flowlab}"
SOLVER="${SOLVER:-direct}"
if [[ "${VARIANT}" == *aes* ]] || [[ "${DESIGN_ID:-}" == *aes* ]]; then
  echo "REFUSED: Dynamic IR cloud wrapper is GCD-only. AES Krylov is not runnable here." >&2
  exit 2
fi
case "${SOLVER}" in
  direct|amg|ras|krylov) ;;
  *)
    echo "REFUSED: SOLVER=${SOLVER} (attesi: direct|amg|ras|krylov)" >&2
    exit 2
    ;;
esac

FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
ODB="${RES}/6_final.odb"
SPICE="${RES}/pdn/pg_vdd_bumps.sp"
INSTS="${RES}/pdn/inst_power_map.json"
STA="${ROOT}/learn/sim/reports/sta_arrivals_${VARIANT}.json"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
LEF="${FLOW}/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef"
SPEF="${RES}/6_final.spef"
SDC="${FLOW}/designs/nangate45/gcd-tutorial/constraint.sdc"
[[ -f "${ODB}" ]] || { echo "FAIL manca ${ODB} — esegui ./scripts/run_gcd_finish_cloud.sh" >&2; exit 1; }

SKIP=(--no-scenarios --no-electrothermal --skip-ngspice --no-vrm)
case "${SOLVER}" in
  direct) SKIP+=(--no-amg --no-ras --no-mor) ;;
  amg)    SKIP+=(--no-ras --no-mor) ;;
  ras)    SKIP+=(--no-amg --no-mor) ;;
  krylov) SKIP+=(--no-amg --no-ras) ;;
esac

AS_BYTES="${PDN_AS_BYTES:-8589934592}"
CPU_S="${PDN_CPU_S:-180}"
export PYTHONPATH="${ROOT}/learn:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "${ROOT}/learn/sim/reports" "${RES}/pdn" /tmp/pd-flow-runs
OUT="${ROOT}/learn/sim/reports/dynamic_ir_${VARIANT}_${SOLVER}.json"
LOG="${ROOT}/learn/sim/reports/dynamic_ir_${VARIANT}_${SOLVER}.log"
echo "GCD dynamic IR cloud: variant=${VARIANT} solver=${SOLVER} as=${AS_BYTES}" | tee "${LOG}"

if [[ ! -f "${INSTS}" ]]; then
  echo "=== export inst_power_map ===" | tee -a "${LOG}"
  prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
    openroad -python -no_init -exit \
      "${ROOT}/learn/scripts/export_odb_inst_power.py" "${ODB}" "${INSTS}" \
      2>&1 | tee -a "${LOG}"
fi
[[ -f "${INSTS}" ]] || { echo "FAIL manca ${INSTS}" >&2; exit 1; }

if [[ ! -f "${SPICE}" ]]; then
  echo "=== write_pg_spice -net VDD ===" | tee -a "${LOG}"
  ACTIVITY_TCL="$(power_activity_tcl "${ROOT}")"
  PKG_R="${PKG_R:-0.05}"
  cd "${FLOW}"
  prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
    openroad -no_init -no_splash -exit <<EOF | tee -a "${LOG}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
${ACTIVITY_TCL}
report_power
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 -bump_size 70 -bump_interval 3 -external_resistance ${PKG_R}
analyze_power_grid -net VDD -source_type BUMPS
write_pg_spice -net VDD -source_type BUMPS ${SPICE}
puts DYNAMIC_IR_SPICE_VDD_DONE
EOF
fi
[[ -f "${SPICE}" ]] || { echo "FAIL manca ${SPICE}" >&2; exit 1; }
n_r="$(grep -cE '^[Rr]' "${SPICE}" || true)"
n_r="${n_r:-0}"
echo "spice n_r=${n_r}" | tee -a "${LOG}"
if [[ "${n_r}" -gt 20000 ]]; then
  echo "REFUSED: n_r=${n_r} is AES-sized — this wrapper is GCD-only." >&2
  exit 2
fi

if [[ ! -f "${STA}" ]]; then
  echo "=== OpenSTA report_arrival ===" | tee -a "${LOG}"
  STA_LIB="${LIB}" STA_V="${RES}/6_final.v" STA_SDC="${SDC}" FLOW_VARIANT="${VARIANT}" \
    prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
    python3 "${ROOT}/learn/scripts/export_sta_arrivals.py" 2>&1 | tee -a "${LOG}"
fi

EXTRA=()
[[ -f "${LEF}" ]] && EXTRA+=(--lef "${LEF}")
[[ -f "${STA}" ]] && EXTRA+=(--sta "${STA}")
[[ -f "${SPEF}" ]] && EXTRA+=(--spef "${SPEF}")

set +e
prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
  python3 -u "${ROOT}/learn/scripts/pdn_dynamic.py" \
    --spice "${SPICE}" \
    --insts "${INSTS}" \
    --out "${OUT}" \
    --mode "${DYNAMIC_IR_MODE:-clock}" \
    --period-ns "${PERIOD_NS:-0.46}" \
    --dur-ns "${DUR_NS:-0.08}" \
    --t50-ns "${T50_NS:-0.12}" \
    --pkg-r "${PKG_R:-0.05}" \
    --pkg-l "${PKG_L:-2e-10}" \
    --c-decap "${C_DECAP:-50e-15}" \
    --dt-ps "${DT_PS:-10}" \
    --liberty "${LIB}" \
    "${EXTRA[@]}" \
    "${SKIP[@]}" \
    2>&1 | tee -a "${LOG}"
rc=${PIPESTATUS[0]}
set -e
[[ -f "${OUT}" ]] || { echo "FAIL manca ${OUT}" >&2; exit 1; }
echo "OK dynamic IR ${VARIANT} solver=${SOLVER} rc=${rc} report=${OUT}"
exit "${rc}"

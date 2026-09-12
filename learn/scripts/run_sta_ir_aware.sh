#!/usr/bin/env bash
# Educational IR-aware STA: OpenSTA worst path × per-cell ITerm V.
# Does not change nominal WNS/TNS. Uses only artifacts from the current run.
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" sta-ir-aware bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
VARIANT="${FLOW_VARIANT:-flowlab}"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
OUT_DIR="${ROOT}/learn/sim/reports"
OUT="${OUT_DIR}/sta_ir_aware_${VARIANT}.json"

# Current-run I(t) map only; no fallback to another variant or map.
MAP="${OUT_DIR}/dynamic_ir_${VARIANT}_direct.map.csv"

# Dynamic IR writes the arrivals artifact into its run-scoped generated
# workspace.  Prefer that artifact over the legacy report location so a
# freshly completed run cannot accidentally consume an older report with the
# same variant name.  Keep the report-root path as an explicit compatibility
# path for users who run export_sta_arrivals.py independently.
if [[ -n "${PD_FLOW_GENERATED_ROOT:-}" ]]; then
  GENERATED_ROOT="$(realpath -m -- "${PD_FLOW_GENERATED_ROOT}")"
elif [[ -n "${PD_FLOW_WORK_HOME:-}" ]]; then
  GENERATED_ROOT="$(realpath -m -- "${PD_FLOW_WORK_HOME}/generated/dynamic_ir/finish")"
else
  GENERATED_ROOT="$(realpath -m -- "${ROOT}/.pdflow/generated/${VARIANT}/finish/dynamic_ir")"
fi
case "${GENERATED_ROOT}" in
  "${ROOT}/.pdflow/"*|"${ROOT}/.pdflow"|"${PD_FLOW_WORK_HOME:-__no_candidate__}/generated/"*) ;;
  *)
    echo "REFUSED: generated STA workspace must remain repository/candidate scoped: ${GENERATED_ROOT}" >&2
    exit 2
    ;;
esac
GENERATED_STA="${GENERATED_ROOT}/mesh/sta_arrivals.json"
REPORT_STA="${OUT_DIR}/sta_arrivals_${VARIANT}.json"
STA=""
STA_SOURCE=""
if [[ -f "${GENERATED_STA}" ]]; then
  STA="${GENERATED_STA}"
  STA_SOURCE="current-run generated workspace"
elif [[ -f "${REPORT_STA}" ]]; then
  STA="${REPORT_STA}"
  STA_SOURCE="explicit report-root compatibility path"
fi

# Use the same run-scoped Dynamic IR mesh for the SPICE input when it is
# available.  The ORFS result directory remains a compatibility fallback for
# older flows that materialised pg_vdd there instead of under .pdflow.
SPICE=""
for candidate in \
  "${GENERATED_ROOT}/mesh/pg_vdd_bumps.sp" \
  "${GENERATED_ROOT}/mesh/pg_vdd.sp" \
  "${RES}/pdn/pg_vdd_bumps.sp" \
  "${RES}/pdn/pg_vdd.sp"; do
  if [[ -f "${candidate}" ]]; then
    SPICE="${candidate}"
    break
  fi
done

export PYTHONPATH="${ROOT}/learn/scripts:/usr/lib/python3/dist-packages${PYTHONPATH:+:${PYTHONPATH}}"

[[ -n "${STA}" ]] || {
  echo "FAIL missing current-run STA arrivals: ${GENERATED_STA}" >&2
  echo "      compatibility path also absent: ${REPORT_STA}" >&2
  echo "      run dynamic_ir or export_sta_arrivals first" >&2
  exit 1
}
[[ -n "${SPICE}" ]] || {
  echo "FAIL missing current-run Dynamic IR SPICE mesh under ${GENERATED_ROOT}/mesh" >&2
  echo "      compatibility paths under ${RES}/pdn are also absent" >&2
  echo "      run chip_pdn_ir / dynamic_ir / write_pg_spice first" >&2
  exit 1
}
[[ -f "${MAP}" ]] || { echo "FAIL missing ${MAP} — run dynamic_ir current_run first"; exit 1; }

mkdir -p "${OUT_DIR}"
echo "STA arrivals source: ${STA_SOURCE} (${STA})"
echo "Dynamic IR SPICE source: ${SPICE}"
python3 "${ROOT}/learn/scripts/sta_ir_aware.py" \
  --sta "${STA}" \
  --spice "${SPICE}" \
  --map "${MAP}" \
  --out "${OUT}" \
  --variant "${VARIANT}"
echo "STA_IR_AWARE_JSON ${OUT}"

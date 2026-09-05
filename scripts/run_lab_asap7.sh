#!/usr/bin/env bash
# Lab-only ASAP7 RTL→GDS. Never writes Nangate flowlab/learn/base.
# Never runs the course signoff orchestrator. Never restamps gold Dynamic IR 45.298 mV.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
TARGET="${1:-finish}"

export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:$PYTHONPATH}"
SPEC_JSON="$(python3 "${ROOT}/learn/scripts/lab_asap7_spec.py")"

VARIANT="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["variant"])' "${SPEC_JSON}")"
CONFIG_REL="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["config"])' "${SPEC_JSON}")"
NICKNAME="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["nickname"])' "${SPEC_JSON}")"
CORNER="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["corner"])' "${SPEC_JSON}")"
VT="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["vt"])' "${SPEC_JSON}")"
LIB_MODEL="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["lib_model"])' "${SPEC_JSON}")"
TRACK="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["track"])' "${SPEC_JSON}")"
CLUSTER="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["cluster"])' "${SPEC_JSON}")"
CLK_PS="$(python3 -c 'import json,sys; v=json.loads(sys.argv[1])["clk_ps"]; print("" if v is None else v)' "${SPEC_JSON}")"

LOCKED='^(flowlab|learn|base)$'
if [[ "${VARIANT}" =~ ${LOCKED} ]]; then
  echo "REFUSED: FLOW_VARIANT=${VARIANT} is locked." >&2
  exit 2
fi
if [[ "${VARIANT}" != lab_asap7_* ]]; then
  echo "REFUSED: lab ASAP7 variant must start with lab_asap7_" >&2
  exit 2
fi
if [[ "${VARIANT}" == *krylov* ]]; then
  echo "REFUSED: Krylov is not a lab ASAP7 variant." >&2
  exit 2
fi
if [[ "${TRACK}" == "6" ]]; then
  echo "REFUSED: 6-track cook is fetch-gated in this pass (views not wired into ORFS make yet)." >&2
  echo "7.5-track is the RTL→GDS path. Fetch 6T with learn/scripts/fetch_asap7_sc6t.sh" >&2
  exit 2
fi

[[ -f "${FLOW}/${CONFIG_REL}" ]] || { echo "FAIL missing ${FLOW}/${CONFIG_REL}" >&2; exit 1; }

MAKE_EXTRA=(
  DESIGN_CONFIG="./${CONFIG_REL}"
  FLOW_VARIANT="${VARIANT}"
  PLATFORM=asap7
  CORNER="${CORNER}"
  LIB_MODEL="${LIB_MODEL}"
  ASAP7_USE_VT="${VT}"
  OPENROAD_EXE="${OPENROAD_EXE:-$(command -v openroad)}"
  OPENSTA_EXE="${OPENSTA_EXE:-$(command -v sta)}"
  YOSYS_EXE="${YOSYS_EXE:-$(command -v yosys)}"
)
if [[ "${CLUSTER}" == "1" ]]; then
  MAKE_EXTRA+=( CLUSTER_FLOPS=1 )
fi
# CCS TC/WC: ORFS config.mk only defines BC_CCS_LIB_FILES. Pass extras when present.
if [[ "${LIB_MODEL}" == "CCS" ]]; then
  CCS_ASSIGN="$(python3 -c 'from dse.asap7_lab import ccs_make_assignment, spec_from_env, validate; s=validate(spec_from_env()); print(ccs_make_assignment(s.corner, s.primary_vt))')"
  if [[ -z "${CCS_ASSIGN}" ]]; then
    echo "REFUSED: CCS liberty list empty for CORNER=${CORNER} VT=${VT}" >&2
    exit 2
  fi
  MAKE_EXTRA+=( "${CCS_ASSIGN}" )
fi
# Optional ORFS knobs. No design-name branch.
# WC leftover: 65% die overflows CTS after setup repair. Default a larger die.
if [[ -n "${CORE_UTILIZATION:-}" ]]; then
  MAKE_EXTRA+=( CORE_UTILIZATION="${CORE_UTILIZATION}" )
elif [[ "${CORNER}" == "WC" ]]; then
  MAKE_EXTRA+=( CORE_UTILIZATION=40 )
fi
if [[ -n "${PLACE_DENSITY:-}" ]]; then
  MAKE_EXTRA+=( PLACE_DENSITY="${PLACE_DENSITY}" )
fi
# Some configs set SYNTH_HDL_FRONTEND=slang. If slang.so is missing, use Yosys.
# Capability / config-file gate — not a design-name branch.
if [[ -n "${SYNTH_HDL_FRONTEND+x}" ]]; then
  MAKE_EXTRA+=( SYNTH_HDL_FRONTEND="${SYNTH_HDL_FRONTEND}" )
elif grep -qE 'SYNTH_HDL_FRONTEND[[:space:]]*=[[:space:]]*slang' "${FLOW}/${CONFIG_REL}"; then
  SLANG_SO=""
  if command -v yosys-config >/dev/null 2>&1; then
    YDAT="$(yosys-config --datdir 2>/dev/null || true)"
    if [[ -n "${YDAT}" && -f "${YDAT}/plugins/slang.so" ]]; then
      SLANG_SO=1
    fi
  fi
  if [[ -z "${SLANG_SO}" ]]; then
    MAKE_EXTRA+=( SYNTH_HDL_FRONTEND= )
    if [[ -z "${EQUIVALENCE_CHECK:-}" ]]; then
      MAKE_EXTRA+=( EQUIVALENCE_CHECK=0 )
    fi
  fi
fi
if [[ -n "${EQUIVALENCE_CHECK:-}" ]]; then
  MAKE_EXTRA+=( EQUIVALENCE_CHECK="${EQUIVALENCE_CHECK}" )
fi
if [[ -n "${CLK_PS}" ]]; then
  # ASAP7 liberty time_unit is 1ps. Do not rewrite to the course 0.46 ns SDC.
  # Written in Python so bash set -u cannot expand $clk_port_name.
  SDC_DIR="${ROOT}/learn/sim/dse/sdc"
  mkdir -p "${SDC_DIR}"
  SDC_FILE="${SDC_DIR}/asap7_${VARIANT}.sdc"
  python3 -c 'import os,sys; from pathlib import Path; from dse.asap7_lab import write_constraint_sdc; write_constraint_sdc(Path(sys.argv[1]), float(sys.argv[2]), sys.argv[3])' \
    "${SDC_FILE}" "${CLK_PS}" "${NICKNAME}"
  MAKE_EXTRA+=( SDC_FILE="${SDC_FILE}" )
fi

AS_BYTES="${PDN_AS_BYTES:-8589934592}"
CPU_S="${PDN_CPU_S:-1800}"

echo "lab asap7 ${TARGET}: variant=${VARIANT} config=${CONFIG_REL} corner=${CORNER} vt=${VT} lib=${LIB_MODEL} track=${TRACK}"

cd "${FLOW}"
set +e
prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
  make \
    "${MAKE_EXTRA[@]}" \
    "${TARGET}"
RC=$?
set -e

python3 - <<PY
from dse.asap7_lab import collect_report, spec_from_env, validate, write_report
spec = validate(spec_from_env())
payload = collect_report(spec, extra={"exit_code": ${RC}})
write_report(payload)
print("lab_asap7 report", payload.get("gds"), "ok", payload.get("ok"))
PY

exit "${RC}"

#!/usr/bin/env bash
# Run one allowlisted FlowLab ORFS stage through the PDflow local agent.
#
# The caller supplies only validated scalar environment values. The stage is
# intentionally fixed by the action registry; arbitrary make targets and
# arbitrary make variables never come from the UI.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" flowlab-stage bash "${BASH_SOURCE[0]}" "$@"
fi
if [[ -f "${ROOT}/scripts/native_eda_env.sh" ]]; then
  source "${ROOT}/scripts/native_eda_env.sh"
fi
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
STAGE="${1:-}"
WORK_HOME="${PD_FLOW_WORK_HOME:-}"

case "${STAGE}" in
  synth|floorplan|place|cts|route|finish) ;;
  *)
    echo "FAIL invalid FlowLab stage: ${STAGE}" >&2
    exit 2
    ;;
esac

if [[ ! -d "${FLOW}" ]]; then
  echo "FAIL missing ORFS flow tree: ${FLOW}" >&2
  exit 1
fi

# A completed FlowLab finish is immutable. Candidate recooks are allowed only
# when the local agent supplies the exact run-scoped WORK_HOME and RTL snapshot
# created by a `flowlab-candidate` run. Never accept an arbitrary output path.
if [[ -n "${WORK_HOME}" ]]; then
  CANDIDATE_RUN_ID="${PD_FLOW_CANDIDATE_RUN_ID:-}"
  if [[ ! "${CANDIDATE_RUN_ID}" =~ ^[A-Za-z0-9_.-]{8,100}$ ]]; then
    echo "FAIL invalid FlowLab candidate run id" >&2
    exit 1
  fi
  EXPECTED_WORK_HOME="${ROOT}/.pdflow/runs/${CANDIDATE_RUN_ID}/candidate/orfs"
  EXPECTED_RTL="${ROOT}/.pdflow/runs/${CANDIDATE_RUN_ID}/candidate/inputs/gcd.v"
  if [[ "${WORK_HOME}" != "${EXPECTED_WORK_HOME}" || "${PD_FLOW_RTL_FILE:-}" != "${EXPECTED_RTL}" ]]; then
    echo "FAIL candidate workspace is outside the requested run" >&2
    exit 1
  fi
  if [[ ! -f "${PD_FLOW_RTL_FILE}" ]]; then
    echo "FAIL missing candidate RTL snapshot: ${PD_FLOW_RTL_FILE}" >&2
    exit 1
  fi
  mkdir -p "${WORK_HOME}"
fi

DESIGN_CONFIG="./designs/nangate45/gcd-tutorial/config.mk"
TUTORIAL_SRC="${ROOT}/learn/designs/nangate45/gcd-tutorial"
TUTORIAL_LINK="${FLOW}/designs/nangate45/gcd-tutorial"
if [[ ! -d "${TUTORIAL_SRC}" ]]; then
  echo "FAIL missing FlowLab tutorial source: ${TUTORIAL_SRC}" >&2
  exit 1
fi

# The link is repository-owned setup state. Refuse an unexpected real
# directory instead of replacing user data from a desktop action.
if [[ -e "${TUTORIAL_LINK}" && ! -L "${TUTORIAL_LINK}" ]]; then
  echo "FAIL tutorial destination is not a symlink: ${TUTORIAL_LINK}" >&2
  exit 1
fi
if [[ -L "${TUTORIAL_LINK}" ]]; then
  if [[ "$(readlink -f "${TUTORIAL_LINK}")" != "$(readlink -f "${TUTORIAL_SRC}")" ]]; then
    echo "FAIL tutorial symlink points outside the FlowLab source: ${TUTORIAL_LINK}" >&2
    exit 1
  fi
else
  ln -s "${TUTORIAL_SRC}" "${TUTORIAL_LINK}"
fi

export FLOW_VARIANT="flowlab"
export VERILOG_FILES="${VERILOG_FILES:-${PD_FLOW_RTL_FILE:-${ROOT}/learn/flowlab/gcd.v}}"
export CORE_UTILIZATION="${CORE_UTILIZATION:-35}"
export PLACE_DENSITY_LB_ADDON="${PLACE_DENSITY_LB_ADDON:-0.2}"
export ABC_AREA="${ABC_AREA:-1}"
export SDC_FILE="${SDC_FILE:-./designs/nangate45/gcd-tutorial/constraint.sdc}"
export TNS_END_PERCENT="${TNS_END_PERCENT:-100}"
export OPENROAD_EXE="${OPENROAD_EXE:-openroad}"
export OPENSTA_EXE="${OPENSTA_EXE:-sta}"
export YOSYS_EXE="${YOSYS_EXE:-yosys}"

echo "== FlowLab ${STAGE} · variant=${FLOW_VARIANT} · timeout=600s =="
cd "${FLOW}"
exec make \
  WORK_HOME="${WORK_HOME:-.}" \
  DESIGN_CONFIG="${DESIGN_CONFIG}" \
  FLOW_VARIANT="${FLOW_VARIANT}" \
  VERILOG_FILES="${VERILOG_FILES}" \
  CORE_UTILIZATION="${CORE_UTILIZATION}" \
  PLACE_DENSITY_LB_ADDON="${PLACE_DENSITY_LB_ADDON}" \
  ABC_AREA="${ABC_AREA}" \
  SDC_FILE="${SDC_FILE}" \
  TNS_END_PERCENT="${TNS_END_PERCENT}" \
  OPENROAD_EXE="${OPENROAD_EXE}" \
  OPENSTA_EXE="${OPENSTA_EXE}" \
  YOSYS_EXE="${YOSYS_EXE}" \
  "${STAGE}"

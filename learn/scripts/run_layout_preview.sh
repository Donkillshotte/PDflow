#!/usr/bin/env bash
# Render one current ODB into an agent-owned generated preview.
#
# This script is intentionally driven only by validated environment values
# supplied by pdflow_agent. It must never write the canonical ORFS results
# tree: finish inputs are read-only and previews live under learn/sim or the
# run-scoped candidate workspace.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Preview rendering is an explicit native job, and the transient resource
# service can have a minimal PATH. Resolve the checked native OpenROAD wrapper
# before doing any filesystem work so a missing environment is reported as a
# controlled GAP rather than a shell command-not-found failure.
if [[ -f "${ROOT}/scripts/native_eda_env.sh" ]]; then
  # shellcheck source=../../scripts/native_eda_env.sh
  source "${ROOT}/scripts/native_eda_env.sh"
fi
PHASE="${PD_FLOW_PREVIEW_PHASE:-}"
VARIANT="${PD_FLOW_PREVIEW_VARIANT:-flowlab}"
RUN_ID="${PD_FLOW_PREVIEW_RUN_ID:-}"

case "${PHASE}" in
  floorplan|pdn|place|cts|route|finish|pkg) ;;
  *)
    echo "PREVIEW_GAP invalid preview phase: ${PHASE}" >&2
    exit 78
    ;;
esac

case "${VARIANT}" in
  flowlab|learn|eco_scratch) ;;
  lab_asap7_*)
    if [[ ! "${VARIANT}" =~ ^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$ ]]; then
      echo "PREVIEW_GAP invalid ASAP7 variant" >&2
      exit 78
    fi
    ;;
  *)
    echo "PREVIEW_GAP invalid preview variant: ${VARIANT}" >&2
    exit 78
    ;;
esac

if [[ -n "${RUN_ID}" && ! "${RUN_ID}" =~ ^[A-Za-z0-9_.-]{8,100}$ ]]; then
  echo "PREVIEW_GAP invalid candidate run id" >&2
  exit 78
fi

ODB_NAME="2_4_floorplan_pdn.odb"
case "${PHASE}" in
  place) ODB_NAME="3_5_place_dp.odb" ;;
  cts) ODB_NAME="4_cts.odb" ;;
  route) ODB_NAME="5_2_route.odb" ;;
  finish|pkg) ODB_NAME="6_final.odb" ;;
esac

if [[ -n "${RUN_ID}" ]]; then
  # Candidate runs are always FlowLab runs. The agent verifies the manifest
  # before setting this variable; retain the check here as defense in depth.
  if [[ "${VARIANT}" != "flowlab" ]]; then
    echo "PREVIEW_GAP candidate previews require the FlowLab variant" >&2
    exit 78
  fi
  CANDIDATE_ROOT="${ROOT}/.pdflow/runs/${RUN_ID}/candidate/orfs"
  ODB_DIR="${CANDIDATE_ROOT}/results/nangate45/gcd/flowlab"
  OUT_DIR="${CANDIDATE_ROOT}/previews/flowlab"
else
  if [[ "${VARIANT}" == lab_asap7_* ]]; then
    ODB_DIR="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/asap7/gcd/${VARIANT}"
  else
    ODB_DIR="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}"
  fi
  OUT_DIR="${ROOT}/learn/sim/previews/${VARIANT}"
fi

ODB_FILE="${ODB_DIR}/${ODB_NAME}"
OUT_FILE="${OUT_DIR}/${PHASE}.png"
TCL="${ROOT}/learn/scripts/capture_gui_shots.tcl"

if [[ ! -f "${ODB_FILE}" ]]; then
  echo "PREVIEW_GAP missing ODB: ${ODB_FILE}" >&2
  exit 78
fi
if [[ ! -f "${TCL}" ]]; then
  echo "PREVIEW_GAP missing capture script: ${TCL}" >&2
  exit 78
fi
OPENROAD_COMMAND="${OPENROAD_EXE:-}"
if [[ -z "${OPENROAD_COMMAND}" ]]; then
  OPENROAD_COMMAND="$(command -v openroad || true)"
fi
if [[ -z "${OPENROAD_COMMAND}" || ! -x "${OPENROAD_COMMAND}" ]]; then
  echo "PREVIEW_GAP native OpenROAD is not available in the configured toolchain" >&2
  exit 78
fi

mkdir -p "${OUT_DIR}"
DISPLAY_VALUE="${DISPLAY:-${WAYLAND_DISPLAY:-${STUDIO_DISPLAY:-:1}}}"
echo "PREVIEW_START phase=${PHASE} variant=${VARIANT} odb=${ODB_FILE} output=${OUT_FILE}"
ODB_FILE="${ODB_FILE}" \
  SHOT_DIR="${OUT_DIR}" \
  SHOT_STEM="${PHASE}" \
  DISPLAY="${DISPLAY_VALUE}" \
  "${OPENROAD_COMMAND}" -no_init -no_splash -exit "${TCL}"

if [[ ! -s "${OUT_FILE}" ]]; then
  echo "PREVIEW_FAIL OpenROAD did not produce ${OUT_FILE}" >&2
  exit 1
fi
echo "PREVIEW_WROTE ${OUT_FILE}"

#!/usr/bin/env bash
# Leftover-named ASAP7 on-die chip PDN mesh (tier B).
# OpenROAD write_pg_spice + pdn_transient.py. Not System PDN (lab_asap7_pkg).
# Writes only the selected ASAP7 artifacts and never imports another design's IR.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" lab-asap7-chip-pdn bash "${BASH_SOURCE[0]}" "$@"
fi
# shellcheck source=learn/lib/lab_tools.sh
source "${ROOT}/learn/lib/lab_tools.sh"
lab_tools_path "${ROOT}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:$PYTHONPATH}"

PDN_ARGS=()
if [[ -n "${LAB_ASAP7_VARIANT:-}" ]]; then
  PDN_ARGS+=(--variant "${LAB_ASAP7_VARIANT}")
fi
python3 "${ROOT}/learn/scripts/lab_asap7_chip_pdn.py" "${PDN_ARGS[@]}" "$@"
echo "leftover-named ASAP7 chip PDN mesh done. Not a product win."

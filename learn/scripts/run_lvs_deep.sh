#!/usr/bin/env bash
# Deeper LVS (filter + VTL tolerances + black-box). Does not fake .lvs.ok.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" lvs-deep bash "${BASH_SOURCE[0]}" "$@"
fi
export FLOW_VARIANT="${FLOW_VARIANT:-flowlab}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "${ROOT}/learn/scripts/run_lvs_deep.py"

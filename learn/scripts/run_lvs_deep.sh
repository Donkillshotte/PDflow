#!/usr/bin/env bash
# Deeper LVS (filter + VTL tolerances + black-box). Does not fake .lvs.ok.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export FLOW_VARIANT="${FLOW_VARIANT:-flowlab}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "${ROOT}/learn/scripts/run_lvs_deep.py"

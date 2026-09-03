#!/usr/bin/env bash
# Minimal ECO propose/apply. Does not run signoff_all.
# Env: FLOW_VARIANT  ECO_MODE=propose|apply  ECO_HOLD=0|1
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 "${ROOT}/learn/scripts/run_eco.py"

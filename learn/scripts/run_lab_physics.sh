#!/usr/bin/env bash
# Rail-scale / same-mesh checks on real-design artifacts. Does not restamp gold.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${ROOT}/learn/scripts${PYTHONPATH:+:${PYTHONPATH}}"
python3 "${ROOT}/learn/scripts/validate_lab_physics.py"
echo "LAB_PHYSICS_JSON ${ROOT}/learn/sim/reports/lab_physics_flowlab.json"
echo "LAB_PHYSICS_LEDGER ${ROOT}/learn/sim/dse/lab_physics_ledger.json"

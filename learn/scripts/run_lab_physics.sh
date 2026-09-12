#!/usr/bin/env bash
# Rail-scale / same-mesh checks on real-design artifacts. Uses current artifacts only.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" lab-physics bash "${BASH_SOURCE[0]}" "$@"
fi
export PYTHONPATH="${ROOT}/learn/scripts${PYTHONPATH:+:${PYTHONPATH}}"
python3 "${ROOT}/learn/scripts/validate_lab_physics.py"
echo "LAB_PHYSICS_JSON ${ROOT}/learn/sim/reports/lab_physics_flowlab.json"
echo "LAB_PHYSICS_LEDGER ${ROOT}/learn/sim/dse/lab_physics_ledger.json"

#!/usr/bin/env bash
# Multi-fidelity DSE: e-graph dpath + BOiLS SSK-GP + current F2/F3/F4 ingest.
# Does not flatten ABC ops with place density or mix extracts.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" dse \
    bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
export PYTHONPATH="${ROOT}/learn:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
VARIANT="${FLOW_VARIANT:-flowlab}"
python3 "${ROOT}/learn/scripts/run_dse.py" \
  --variant "${VARIANT}" \
  --budget-s "${DSE_BUDGET_S:-45}" \
  --f1-max "${DSE_F1_MAX:-6}"
python3 "${ROOT}/learn/scripts/record_dse_launch.py" --variant "${VARIANT}"
echo "OK dse ${VARIANT}"

#!/usr/bin/env bash
# Multi-fidelity DSE: e-graph dpath + BOiLS SSK-GP + ingest F2/F3/F4.
# Does not flatten ABC ops with place density. Does not replace Dynamic IR gold.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${ROOT}/learn:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
VARIANT="${FLOW_VARIANT:-flowlab}"
python3 "${ROOT}/learn/scripts/run_dse.py" \
  --variant "${VARIANT}" \
  --budget-s "${DSE_BUDGET_S:-45}" \
  --f1-max "${DSE_F1_MAX:-6}"
python3 "${ROOT}/learn/scripts/record_dse_launch.py" --variant "${VARIANT}" --seed-ingest
echo "OK dse ${VARIANT}"

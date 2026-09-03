#!/usr/bin/env bash
# Educational GCD-combo CCS re-char (PTM 45 nm + Nangate CDL). Official lib stays NLDM.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export FLOW_VARIANT="${FLOW_VARIANT:-flowlab}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "${ROOT}/learn/scripts/char_nangate_ccs.py"

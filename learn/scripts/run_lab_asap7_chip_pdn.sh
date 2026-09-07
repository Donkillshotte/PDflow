#!/usr/bin/env bash
# Leftover-named ASAP7 on-die chip PDN mesh (tier B).
# OpenROAD write_pg_spice + pdn_transient.py. Not System PDN (lab_asap7_pkg).
# Never writes nangate45/gcd/flowlab. Never restamps gold Dynamic IR 45.298 mV.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=learn/lib/lab_tools.sh
source "${ROOT}/learn/lib/lab_tools.sh"
lab_tools_path "${ROOT}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:$PYTHONPATH}"

python3 "${ROOT}/learn/scripts/lab_asap7_chip_pdn.py" "$@"
echo "leftover-named ASAP7 chip PDN mesh done. Not a product win."

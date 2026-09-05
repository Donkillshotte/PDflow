#!/usr/bin/env bash
# Layer-1 ASAP7 path: fetch public PDK if missing, inventory, leftover Xyce inverter.
# Never stamps .lvs.ok. Does not restamp gold 45.298 mV. Not a product win.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=learn/lib/lab_tools.sh
source "${ROOT}/learn/lib/lab_tools.sh"
lab_tools_path "${ROOT}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:$PYTHONPATH}"

if [[ ! -f "${ROOT}/learn/lab/asap7/pdk/models/hspice/7nm_TT_160803.pm" && ! -f "${ROOT}/learn/lab/asap7/pdk/models/hspice/7nm_TT.pm" ]]; then
  "${ROOT}/learn/scripts/fetch_asap7_pdk.sh"
fi
python3 "${ROOT}/learn/scripts/lab_asap7_pdk.py"
python3 "${ROOT}/learn/scripts/lab_asap7_spice.py"
echo "layer-1 leftover-named path done. Calibre stays gated."

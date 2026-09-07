#!/usr/bin/env bash
# Leftover-named ASAP7 PKG: dummy bump + sidecar RDL + compact ladder.
# Dummy, not C4. Lumped RLC, not Touchstone. Not a product win.
# Never writes lab_asap7_*/6_final.odb. Never writes nangate45/gcd/flowlab.
# Never restamps gold Dynamic IR 45.298 mV.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=learn/lib/lab_tools.sh
source "${ROOT}/learn/lib/lab_tools.sh"
lab_tools_path "${ROOT}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:$PYTHONPATH}"

python3 "${ROOT}/learn/scripts/lab_asap7_pkg.py" "$@"
echo "leftover-named ASAP7 PKG done. Dummy, not C4. Not a product win."

#!/usr/bin/env bash
# Leftover-named ASAP7 PKG: dummy bump + sidecar RDL + compact ladder.
# Dummy, not C4. Lumped RLC, not Touchstone. Not a product win.
# Never writes lab_asap7_*/6_final.odb. Never writes nangate45/gcd/flowlab.
# Uses only the current ASAP7 artifacts; it does not import another design's IR.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" lab-asap7-pkg bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
# shellcheck source=learn/lib/lab_tools.sh
source "${ROOT}/learn/lib/lab_tools.sh"
lab_tools_path "${ROOT}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts${PYTHONPATH:+:$PYTHONPATH}"

PKG_ARGS=()
if [[ -n "${LAB_ASAP7_VARIANT:-}" ]]; then
  PKG_ARGS+=(--variant "${LAB_ASAP7_VARIANT}")
fi
python3 "${ROOT}/learn/scripts/lab_asap7_pkg.py" "${PKG_ARGS[@]}" "$@"
echo "leftover-named ASAP7 PKG done. Dummy, not C4. Not a product win."

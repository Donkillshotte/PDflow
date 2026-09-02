#!/usr/bin/env bash
# Run the full RTL -> GDS flow with ORFS on the example "gcd" design
# (Nangate45 PDK): synthesis (yosys), floorplan, place, CTS, route, finish (GDS).
# Results land in tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"

DESIGN_CONFIG="${DESIGN_CONFIG:-./designs/nangate45/gcd/config.mk}"

cd "${FLOW}"
exec make \
  DESIGN_CONFIG="${DESIGN_CONFIG}" \
  CORE_UTILIZATION="${CORE_UTILIZATION:-35}" \
  OPENROAD_EXE="${OPENROAD_EXE:-$(command -v openroad)}" \
  OPENSTA_EXE="${OPENSTA_EXE:-$(command -v sta)}" \
  YOSYS_EXE="${YOSYS_EXE:-$(command -v yosys)}" \
  "$@"

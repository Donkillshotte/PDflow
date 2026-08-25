#!/usr/bin/env bash
# Esegue il flusso completo RTL -> GDS con ORFS sul design di esempio "gcd"
# (PDK Nangate45): sintesi (yosys), floorplan, place, CTS, route, finish (GDS).
# I risultati finiscono in tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"

DESIGN_CONFIG="${DESIGN_CONFIG:-./designs/nangate45/gcd/config.mk}"

cd "${FLOW}"
exec make DESIGN_CONFIG="${DESIGN_CONFIG}" "$@"

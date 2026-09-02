#!/usr/bin/env bash
# KLayout DRC on 6_final.gds (FreePDK45.lydrc) via ORFS make drc.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
GDS="${FLOW}/results/nangate45/gcd/learn/6_final.gds"
[[ -f "${GDS}" ]] || { echo "FAIL missing GDS — run finish first"; exit 1; }

cd "${FLOW}"
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 \
     OPENROAD_EXE="${OPENROAD_EXE:-openroad}" \
     OPENSTA_EXE="${OPENSTA_EXE:-sta}" \
     YOSYS_EXE="${YOSYS_EXE:-yosys}" \
     drc | tee /tmp/klayout-drc.log

RPT="${FLOW}/reports/nangate45/gcd/learn/6_drc.lyrdb"
[[ -f "${RPT}" ]] && echo "OK DRC report ${RPT}" || echo "WARN report missing — see log"
ls -la "${FLOW}/reports/nangate45/gcd/learn/"*drc* 2>/dev/null || true

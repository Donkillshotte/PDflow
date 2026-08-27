#!/usr/bin/env bash
# System / package-aware PDN IR analysis via OpenROAD analyze_power_grid.
# Modes: STRAPS (board straps proxy), FULL (all nodes), BUMPS (C4-like pattern).
# Uso: run_system_pdn.sh
# Env: FLOW_VARIANT=learn|flowlab (default learn)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-learn}"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ODB="${RES}/6_final.odb"
SDC="${FLOW}/designs/nangate45/gcd-tutorial/constraint.sdc"

[[ -f "${ODB}" ]] || { echo "FAIL manca ${ODB} — esegui finish (variant=${VARIANT})"; exit 1; }
[[ -f "${LIB}" ]] || { echo "FAIL manca liberty"; exit 1; }
[[ -f "${SDC}" ]] || { echo "FAIL manca SDC"; exit 1; }

OUT_DIR="${ROOT}/learn/sim/reports"
mkdir -p "${OUT_DIR}"
OUT="${OUT_DIR}/system_pdn_${VARIANT}.log"
STAMP="${RES}/.system_pdn.ok"

cd "${FLOW}"
openroad -no_init -no_splash -exit <<EOF | tee "${OUT}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}

puts "=== SYSTEM_PDN STRAPS (proxy board straps) ==="
analyze_power_grid -net VDD -source_type STRAPS
analyze_power_grid -net VSS -source_type STRAPS

puts "=== SYSTEM_PDN FULL (all metal sources) ==="
analyze_power_grid -net VDD -source_type FULL
analyze_power_grid -net VSS -source_type FULL

puts "=== SYSTEM_PDN BUMPS (C4-like package bumps proxy) ==="
analyze_power_grid -net VDD -source_type BUMPS
analyze_power_grid -net VSS -source_type BUMPS

puts "SYSTEM_PDN_DONE ${VARIANT}"
EOF

rg -q 'SYSTEM_PDN_DONE' "${OUT}"
rg -q 'Worstcase IR drop' "${OUT}"
date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
echo "OK system PDN ${VARIANT} → ${OUT}"
echo "Nota: su GCD nangate45 i bump sono un proxy OpenROAD (PSM-0073), non un package LEF reale."

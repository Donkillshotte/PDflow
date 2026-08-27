#!/usr/bin/env bash
# check_power_grid su ODB PDN / final (grid connectivity).
# Uso: run_gridcheck.sh [pdn|final]
# Env: FLOW_VARIANT=learn|flowlab (default learn)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-learn}"
RES="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}"
STAGE="${1:-pdn}" # pdn | final
case "${STAGE}" in
  pdn) ODB="${RES}/2_4_floorplan_pdn.odb" ;;
  final) ODB="${RES}/6_final.odb" ;;
  *) echo "uso: FLOW_VARIANT=learn|flowlab $0 [pdn|final]"; exit 2 ;;
esac
[[ -f "${ODB}" ]] || { echo "FAIL manca ${ODB} — esegui floorplan/finish (variant=${VARIANT})"; exit 1; }

OUT_DIR="${ROOT}/learn/sim/reports"
mkdir -p "${OUT_DIR}"
OUT="${OUT_DIR}/gridcheck_${VARIANT}_${STAGE}.log"
STAMP="${RES}/.gridcheck_${STAGE}.ok"

openroad -no_init -no_splash -exit <<EOF | tee "${OUT}"
read_db ${ODB}
# Nangate GCD often has no explicit power terminals → allow shape-only check
check_power_grid -net VDD -dont_require_terminals
check_power_grid -net VSS -dont_require_terminals
puts "GRIDCHECK_DONE ${VARIANT} ${STAGE}"
EOF

rg -q 'PSM-0040' "${OUT}"
rg -q 'GRIDCHECK_DONE' "${OUT}"
date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
echo "OK gridcheck ${VARIANT}/${STAGE} → ${OUT}"

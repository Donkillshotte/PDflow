#!/usr/bin/env bash
# check_power_grid su ODB PDN / final (grid connectivity).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RES="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn"
STAGE="${1:-pdn}" # pdn | final
case "${STAGE}" in
  pdn) ODB="${RES}/2_4_floorplan_pdn.odb" ;;
  final) ODB="${RES}/6_final.odb" ;;
  *) echo "uso: $0 [pdn|final]"; exit 2 ;;
esac
[[ -f "${ODB}" ]] || { echo "FAIL manca ${ODB} — esegui floorplan/finish"; exit 1; }

OUT="${ROOT}/learn/sim/reports/gridcheck_${STAGE}.log"
mkdir -p "$(dirname "${OUT}")"

openroad -no_init -no_splash -exit <<EOF | tee "${OUT}"
read_db ${ODB}
# Nangate GCD often has no explicit power terminals → allow shape-only check
check_power_grid -net VDD -dont_require_terminals
check_power_grid -net VSS -dont_require_terminals
puts "GRIDCHECK_DONE ${STAGE}"
EOF

rg -q 'PSM-0040' "${OUT}"
rg -q 'GRIDCHECK_DONE' "${OUT}"
echo "OK gridcheck ${STAGE} → ${OUT}"

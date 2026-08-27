#!/usr/bin/env bash
# Demo attività di switching (senza VCD): set_power_activity + report_power su final.
# Env: FLOW_VARIANT=learn|flowlab (default learn)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-learn}"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ODB="${RES}/6_final.odb"
SDC="${FLOW}/designs/nangate45/gcd-tutorial/constraint.sdc"
[[ -f "${ODB}" ]] || { echo "FAIL manca ${ODB} (variant=${VARIANT})"; exit 1; }

OUT="${ROOT}/learn/sim/reports/activity_power_${VARIANT}.log"
mkdir -p "$(dirname "${OUT}")"

cd "${FLOW}"
openroad -no_init -no_splash -exit <<EOF | tee "${OUT}"
read_liberty ${LIB}
read_db ${ODB}
read_sdc ${SDC}
# Attività globale sintetica (proxy finché non hai VCD da sim RTL)
set_power_activity -global -activity 0.2 -duty 0.5
report_power
puts "ACTIVITY_POWER_DONE ${VARIANT}"
EOF
rg -q 'ACTIVITY_POWER_DONE' "${OUT}"
echo "OK activity power ${VARIANT} → ${OUT}"
echo "Nota: per vettori reali, genera VCD con learn/scripts/run_rtl_sim.sh e usa read_power_activities -vcd …"

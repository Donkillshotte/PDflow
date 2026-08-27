#!/usr/bin/env bash
# Export SPICE netlists + stats into learn/sim/spice/ for study.
#
# Uso: export_spice_lab.sh
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
OUT="${ROOT}/learn/sim/spice"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
MESH="${RES}/pdn/pg_vdd_bumps.sp"
SYS="${RES}/system_pdn"

mkdir -p "${OUT}"

echo "=== export_spice_lab · variant=${VARIANT} ==="

# System PDN netlists (small — always copy)
if [[ -f "${SYS}/tran.sp" ]]; then
  cp "${SYS}/tran.sp" "${OUT}/system_pdn_tran_${VARIANT}.sp"
  cp "${SYS}/ac.sp" "${OUT}/system_pdn_ac_${VARIANT}.sp"
  echo "OK system_pdn tran+ac → ${OUT}"
elif [[ -f "${OUT}/system_pdn_tran_demo.sp" ]]; then
  cp "${OUT}/system_pdn_tran_demo.sp" "${OUT}/system_pdn_tran_${VARIANT}.sp"
  echo "OK demo tran copied (run system_pdn first for live netlist)"
fi

# Chip mesh — copy full if exists, else note
if [[ -f "${MESH}" ]]; then
  cp "${MESH}" "${OUT}/pg_vdd_bumps_${VARIANT}.sp"
  head -120 "${MESH}" > "${OUT}/pg_vdd_header_${VARIANT}.sp"
  echo "* Annotated header — full mesh: pg_vdd_bumps_${VARIANT}.sp" >> "${OUT}/pg_vdd_header_${VARIANT}.sp"
  NR=$(rg -c '^R' "${MESH}" || echo 0)
  NI=$(rg -c '^I' "${MESH}" || echo 0)
  NV=$(rg -c '^V' "${MESH}" || echo 0)
  python3 - <<PY
import json
from pathlib import Path
p = Path("${OUT}/mesh_stats_${VARIANT}.json")
p.write_text(json.dumps({
  "variant": "${VARIANT}",
  "mesh_sp": "pg_vdd_bumps_${VARIANT}.sp",
  "resistors": int("${NR}"),
  "current_sources": int("${NI}"),
  "voltage_sources": int("${NV}"),
  "note": "R=metal grid, I=cell ITerm sinks, V=bump/strap sources"
}, indent=2))
print("stats →", p)
PY
  echo "OK chip mesh ${NR} R · ${NI} I → ${OUT}"
else
  echo "WARN mesh assente — esegui run_chip_pdn_ir.sh dopo finish"
fi

# Config reference
cp "${ROOT}/learn/system_pdn/default.json" "${OUT}/system_pdn_config.json"

cat > "${OUT}/INDEX_${VARIANT}.md" <<MD
# SPICE lab · ${VARIANT}

| File | Descrizione |
|---|---|
| system_pdn_tran_${VARIANT}.sp | Ladder TRAN ngspice |
| system_pdn_ac_${VARIANT}.sp | Ladder AC Z(f) |
| pg_vdd_bumps_${VARIANT}.sp | Mesh chip (se export) |
| pg_vdd_header_${VARIANT}.sp | Prime righe mesh annotate |
| mesh_stats_${VARIANT}.json | Conteggi R/I/V |

Docs: learn/reference/spice-power-chain.md
MD

echo "SPICE_LAB_EXPORT_DONE ${VARIANT}"
echo "OK → ${OUT}/INDEX_${VARIANT}.md"

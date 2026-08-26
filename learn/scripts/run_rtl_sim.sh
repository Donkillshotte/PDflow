#!/usr/bin/env bash
# Simulazione RTL del GCD con Icarus Verilog (+ VCD opzionale).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RTL="${ROOT}/tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v"
TB="${ROOT}/learn/sim/gcd/tb_gcd.v"
OUTDIR="${ROOT}/learn/sim/gcd"
mkdir -p "${OUTDIR}"
cd "${ROOT}"

if ! command -v iverilog >/dev/null; then
  echo "FAIL iverilog non installato (apt install iverilog)"
  exit 1
fi
[[ -f "${RTL}" ]] || { echo "FAIL manca ${RTL}"; exit 1; }

echo "== Compile GCD RTL + TB =="
iverilog -g2012 -o "${OUTDIR}/gcd.vvp" "${RTL}" "${TB}"
echo "== Run =="
cd "${ROOT}"
vvp "${OUTDIR}/gcd.vvp" | tee "${OUTDIR}/sim.log"
rg -q 'RTL_SIM_PASS' "${OUTDIR}/sim.log"
echo "OK VCD=${OUTDIR}/gcd.vcd (se prodotto)"
ls -la "${OUTDIR}/gcd.vcd" 2>/dev/null || true

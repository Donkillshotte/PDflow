#!/usr/bin/env bash
# RTL simulation of GCD with Icarus Verilog (+ optional VCD).
# RTL_FILE can point to learn/flowlab/gcd.v (FlowLab).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RTL="${RTL_FILE:-${ROOT}/tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v}"
TB="${ROOT}/learn/sim/gcd/tb_gcd.v"
OUTDIR="${ROOT}/learn/sim/gcd"
mkdir -p "${OUTDIR}"
cd "${ROOT}"

if ! command -v iverilog >/dev/null; then
  echo "FAIL iverilog not installed (apt install iverilog)"
  exit 1
fi
[[ -f "${RTL}" ]] || { echo "FAIL missing ${RTL}"; exit 1; }

echo "== Compile GCD RTL + TB =="
echo "RTL=${RTL}"
iverilog -g2012 -o "${OUTDIR}/gcd.vvp" "${RTL}" "${TB}"
echo "== Run =="
cd "${ROOT}"
vvp "${OUTDIR}/gcd.vvp" | tee "${OUTDIR}/sim.log"
rg -q 'RTL_SIM_PASS' "${OUTDIR}/sim.log"
echo "OK VCD=${OUTDIR}/gcd.vcd (if produced)"
ls -la "${OUTDIR}/gcd.vcd" 2>/dev/null || true

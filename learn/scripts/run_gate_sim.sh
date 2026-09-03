#!/usr/bin/env bash
# Functional gate-level sim of FlowLab/learn 6_final.v + Nangate behavioral .v.
# Dumps learn/sim/gcd/gcd_gate.vcd for name-join (not SDF).
# Env: FLOW_VARIANT=flowlab|learn
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
NET="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/6_final.v"
CELLS="${ROOT}/learn/platforms/nangate45/verilog/NangateOpenCellLibrary.v"
TB="${ROOT}/learn/sim/gcd/tb_gcd_gate.v"
OUTDIR="${ROOT}/learn/sim/gcd"
JSON="${ROOT}/learn/sim/reports/gate_sim_${VARIANT}.json"
LOG="${OUTDIR}/gate_sim.log"

mkdir -p "${OUTDIR}" "$(dirname "${JSON}")"
cd "${ROOT}"

if ! command -v iverilog >/dev/null; then
  echo "FAIL iverilog not installed"
  exit 1
fi
[[ -f "${NET}" ]] || { echo "FAIL missing ${NET} — run finish first (variant=${VARIANT})"; exit 1; }
[[ -f "${CELLS}" ]] || { echo "FAIL missing ${CELLS}"; exit 1; }
[[ -f "${TB}" ]] || { echo "FAIL missing ${TB}"; exit 1; }

echo "== Compile gate netlist + Nangate .v + TB (functional GLS, no SDF) =="
echo "NET=${NET}"
iverilog -g2012 -o "${OUTDIR}/gcd_gate.vvp" "${CELLS}" "${NET}" "${TB}"
echo "== Run =="
vvp "${OUTDIR}/gcd_gate.vvp" | tee "${LOG}"
rg -q 'GATE_SIM_PASS' "${LOG}"
VCD="${OUTDIR}/gcd_gate.vcd"
[[ -s "${VCD}" ]] || { echo "FAIL missing ${VCD}"; exit 1; }

python3 - <<PY
import json
from pathlib import Path
vcd = Path("${VCD}")
log = Path("${LOG}").read_text(errors="replace")
ok = "GATE_SIM_PASS" in log
out = {
  "kind": "gate_sim",
  "variant": "${VARIANT}",
  "ok": ok,
  "status": "READY" if ok else "FAIL",
  "netlist": "${NET}",
  "cells": "${CELLS}",
  "vcd": str(vcd),
  "vcd_bytes": vcd.stat().st_size if vcd.is_file() else 0,
  "scope": "tb_gcd_gate/dut",
  "educational_note": "Functional GLS (Icarus + Nangate behavioral .v). Not SDF, not timing sign-off.",
  "summary": "GATE_SIM_PASS · gcd_gate.vcd" if ok else "GATE_SIM_FAIL",
}
Path("${JSON}").write_text(json.dumps(out, indent=2) + "\n")
print("GATE_SIM_JSON", "${JSON}")
print(out["summary"])
PY
echo "OK VCD=${VCD}"
ls -la "${VCD}"

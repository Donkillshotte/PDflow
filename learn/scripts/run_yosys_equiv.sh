#!/usr/bin/env bash
# Yosys equivalence: RTL GCD vs Yosys generic synth (EQY-class, no commercial tool).
# Optionally records the ORFS mapped netlist 1_2_yosys.v if present (Nangate cells).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
RTL="${ROOT}/learn/flowlab/gcd.v"
[[ -f "${RTL}" ]] || RTL="${ROOT}/tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v"
MAPPED="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/1_2_yosys.v"
OUT="${ROOT}/learn/sim/reports/yosys_equiv_${VARIANT}.log"
JSON="${ROOT}/learn/sim/reports/yosys_equiv_${VARIANT}.json"
mkdir -p "$(dirname "${OUT}")"

yosys -q -l "${OUT}" -p "
read_verilog ${RTL}
hierarchy -check -top gcd
proc; flatten; opt_expr; opt_clean
design -save rtl
synth -top gcd
opt; clean
design -save syn
design -copy-from rtl -as gold gcd
design -copy-from syn -as gate gcd
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple
equiv_induct
equiv_status
"

python3 - <<PY
import json, re
from pathlib import Path
log = Path(${OUT@Q}).read_text(errors="replace")
ok = bool(re.search(r"Equivalence successfully proven", log, re.I))
if not ok:
    ok = bool(re.search(r"are proven and 0 are unproven", log, re.I))
mapped = Path(${MAPPED@Q})
Path(${JSON@Q}).write_text(json.dumps({
  "ok": ok,
  "kind": "yosys_equiv",
  "variant": ${VARIANT@Q},
  "rtl": ${RTL@Q},
  "mapped_netlist": str(mapped) if mapped.exists() else None,
  "mapped_exists": mapped.exists(),
  "engine": "yosys equiv_make/simple/induct (EQY-class; eqy binary not required)",
  "commercial_gap": "EQY CLI not installed — Yosys native equiv_* is the same engine",
  "summary": "Yosys equiv RTL↔generic-synth " + ("PASS" if ok else "CHECK_LOG"),
  "log": ${OUT@Q},
}, indent=2) + "\n")
print("YOSYS_EQUIV", "PASS" if ok else "CHECK", "→", ${JSON@Q})
raise SystemExit(0 if ok else 1)
PY

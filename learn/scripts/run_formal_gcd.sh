#!/usr/bin/env bash
# Formal safety on GCD via Yosys SAT (SymbiYosys-class backend).
# Property: holding reset implies resp_val stays 0 (synchronous reset).
# Uses sby + z3 if present; otherwise yosys sat -tempinduct.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
RTL="${ROOT}/learn/flowlab/gcd.v"
[[ -f "${RTL}" ]] || RTL="${ROOT}/tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v"
WRAP="${ROOT}/learn/formal/gcd_safety.v"
OUT="${ROOT}/learn/sim/reports/formal_gcd_${VARIANT}.log"
JSON="${ROOT}/learn/sim/reports/formal_gcd_${VARIANT}.json"
mkdir -p "$(dirname "${OUT}")"

ENGINE="yosys-sat-tempinduct"
if command -v sby >/dev/null 2>&1; then
  ENGINE="sby"
  SBY="${ROOT}/learn/formal/gcd_safety.sby"
  cat > "${SBY}" <<SBY
[options]
mode prove
depth 20

[engines]
smtbmc z3

[script]
read -formal ${WRAP} ${RTL}
prep -flatten -top gcd_safety
async2sync
chformal -lower

[files]
${WRAP}
${RTL}
SBY
  sby -f "${SBY}" 2>&1 | tee "${OUT}" || true
else
  yosys -q -l "${OUT}" -p "
read_verilog ${RTL}
hierarchy -check -top gcd
prep -flatten -top gcd
sat -verify -tempinduct -set reset 1 -prove resp_val 0 -set-init-zero
" || true
fi

python3 - <<PY
import json, re, shutil
from pathlib import Path
log = Path(${OUT@Q}).read_text(errors="replace")
ok = bool(re.search(
    r"Induction step proven:\s*SUCCESS|SAT proof finished - no model found:\s*SUCCESS|DONE \(PASS\)|Status:\s*PASS",
    log, re.I))
if re.search(r"proof did fail|SAT proof finished - model found:\s*FAIL|DONE \(FAIL\)|Status:\s*FAIL", log, re.I):
    ok = False
Path(${JSON@Q}).write_text(json.dumps({
  "ok": ok,
  "kind": "formal_gcd",
  "engine": ${ENGINE@Q},
  "sby_present": shutil.which("sby") is not None,
  "z3_present": shutil.which("z3") is not None,
  "property": "reset=1 |-> resp_val=0 (tempinduct)",
  "log": ${OUT@Q},
  "commercial_gap": "SymbiYosys (sby) CLI not installed — Yosys sat tempinduct is the SAT/BMC backend",
  "summary": f"Formal GCD ({${ENGINE@Q}}) " + ("PASS" if ok else "CHECK_LOG"),
}, indent=2) + "\n")
print("FORMAL", "PASS" if ok else "CHECK", "engine", ${ENGINE@Q})
raise SystemExit(0 if ok else 1)
PY

#!/usr/bin/env bash
# One-shot tool matrix: equiv, formal, OpenRCX SPEF, PEX, layout probe,
# spice engines, vectorless/dynamic (if 6_final.odb exists).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
export FLOW_VARIANT="${VARIANT}"
OUT="${ROOT}/learn/sim/reports/tool_matrix_${VARIANT}.json"
mkdir -p "$(dirname "${OUT}")"

echo "=== TOOL MATRIX ${VARIANT} ==="
"${ROOT}/learn/scripts/run_yosys_equiv.sh"
"${ROOT}/learn/scripts/run_formal_gcd.sh"
"${ROOT}/learn/scripts/run_openrcx_report.sh"
python3 "${ROOT}/learn/scripts/run_analytical_pex.py"
"${ROOT}/learn/scripts/run_layout_tools_probe.sh"
"${ROOT}/learn/scripts/run_spice_engines.sh"
if [[ -f "${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/6_final.odb" ]]; then
  "${ROOT}/learn/scripts/run_vectorless.sh"
else
  echo "skip vectorless (no 6_final.odb)"
fi
if [[ -f "${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/pdn/pg_vdd_bumps.sp" ]] \
  || [[ -f "${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/6_final.odb" ]]; then
  "${ROOT}/learn/scripts/run_vyges_em_ir.sh"
else
  echo "skip vyges-em-ir (no finish / spice mesh)"
fi

python3 - <<PY
import json, shutil
from pathlib import Path
root = Path(${ROOT@Q})
rep = root / "learn/sim/reports"
variant = ${VARIANT@Q}

def load(name):
    p = rep / f"{name}_{variant}.json"
    if not p.exists():
        return {"ok": False, "missing": str(p)}
    return json.loads(p.read_text())

parts = {
    "yosys_equiv": load("yosys_equiv"),
    "formal_gcd": load("formal_gcd"),
    "openrcx": load("openrcx"),
    "analytical_pex": load("analytical_pex"),
    "layout_tools": load("layout_tools"),
    "spice_engines": load("spice_engines"),
    "vectorless": load("vectorless"),
    "vyges_em_ir": load("vyges_em_ir"),
}
tools = {
    "yosys": {"status": "INTEGRATED", "bin": shutil.which("yosys"), "role": "synth + equiv + formal sat"},
    "klayout": {"status": "INTEGRATED", "bin": shutil.which("klayout"), "role": "DRC/LVS signoff"},
    "magic": {"status": "PARTIAL" if shutil.which("magic") else "GAP", "bin": shutil.which("magic"), "role": "present, no FreePDK45 tech"},
    "netgen": {"status": "PARTIAL" if (shutil.which("netgen") or shutil.which("netgen-lvs")) else "GAP", "bin": shutil.which("netgen") or shutil.which("netgen-lvs"), "role": "LVS binary present, no Nangate setup"},
    "eqy": {"status": "MAPPED", "bin": shutil.which("eqy"), "role": "Yosys equiv_* is the EQY engine"},
    "symbiyosys": {"status": "MAPPED", "bin": shutil.which("sby"), "role": "Yosys sat (+ z3 if sby)"},
    "ngspice": {"status": "INTEGRATED", "bin": shutil.which("ngspice"), "role": "System PDN + demo TRAN"},
    "xyce": {"status": "GAP" if not (shutil.which("xyce") or shutil.which("Xyce")) else "INTEGRATED", "bin": shutil.which("xyce") or shutil.which("Xyce"), "role": "Sandia parallel SPICE; ngspice covers GCD"},
    "openrcx": {"status": "INTEGRATED", "bin": "openroad extract_parasitics", "role": "6_final.spef from finish"},
    "fastercap": {"status": "MAPPED", "bin": shutil.which("fastercap") or shutil.which("FasterCap"), "role": "Sakurai–Tamaru + 2D FDM"},
    "raphael": {"status": "GAP", "bin": None, "role": "Synopsys commercial — not licensed"},
    "starrc": {"status": "GAP", "bin": None, "role": "Synopsys commercial — OpenRCX SPEF is the extract"},
    "open_pdks": {"status": "GAP", "bin": None, "role": "Sky130/gf180; this course is pinned Nangate45/FreePDK45"},
    "vyges_em_ir": {"status": "INTEGRATED", "bin": shutil.which("vyges-em-ir") or str(root / "tools/vyges-em-ir/vyges-em-ir"), "role": "CG + backward Euler on write_pg_spice mesh"},
}
odb = root / f"tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/{variant}/6_final.odb"
skip_optional = set() if odb.exists() else {"vectorless", "vyges_em_ir"}
ok = all(v.get("ok") for k, v in parts.items() if k not in skip_optional)
out = {
    "ok": ok,
    "kind": "tool_matrix",
    "variant": variant,
    "parts": {k: {"ok": v.get("ok"), "summary": v.get("summary")} for k, v in parts.items()},
    "tools": tools,
    "summary": "tool matrix " + ("PASS" if ok else "CHECK"),
}
Path(${OUT@Q}).write_text(json.dumps(out, indent=2) + "\n")
print(out["summary"], "→", ${OUT@Q})
raise SystemExit(0 if ok else 1)
PY
echo "TOOL_MATRIX_DONE ${VARIANT}"

#!/usr/bin/env python3
"""ASAP7 setup/hold pair on one finished netlist. Lab only. Not a product win.

Hammer default: setup = SS / 0.63 V / 100 °C (our WC); hold = FF / 0.77 V (our BC).
Same Verilog + SPEF + SDC. Two OpenSTA runs. Do not restamp 45.298.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORFS = ROOT / "tools/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM"
OUT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_mmmc.json"
DEFAULT_DIR = (
    ROOT
    / "tools/OpenROAD-flow-scripts/flow/results/asap7/gcd"
    / "lab_asap7_gcd_tc_rvt_nldm_7p5_480ps"
)

CORNER_LIBS = {
    "WC": (
        "asap7sc7p5t_AO_RVT_SS_nldm_211120.lib.gz",
        "asap7sc7p5t_INVBUF_RVT_SS_nldm_220122.lib.gz",
        "asap7sc7p5t_OA_RVT_SS_nldm_211120.lib.gz",
        "asap7sc7p5t_SIMPLE_RVT_SS_nldm_211120.lib.gz",
        "asap7sc7p5t_SEQ_RVT_SS_nldm_220123.lib",
    ),
    "BC": (
        "asap7sc7p5t_AO_RVT_FF_nldm_211120.lib.gz",
        "asap7sc7p5t_INVBUF_RVT_FF_nldm_220122.lib.gz",
        "asap7sc7p5t_OA_RVT_FF_nldm_211120.lib.gz",
        "asap7sc7p5t_SIMPLE_RVT_FF_nldm_211120.lib.gz",
        "asap7sc7p5t_SEQ_RVT_FF_nldm_220123.lib",
    ),
}


def _sta_wns(verilog: Path, spef: Path, sdc: Path, libs: list[Path], path_delay: str) -> dict:
    sta = shutil.which("sta") or os.environ.get("OPENSTA_EXE")
    if not sta:
        return {"ok": False, "reason": "sta missing"}
    missing = [str(p) for p in libs if not p.is_file()]
    if missing:
        return {"ok": False, "reason": f"liberty missing {missing[:2]}"}
    tcl = Path(f"/tmp/lab_asap7_mmmc_{path_delay}.tcl")
    lines = [f"read_liberty {p}" for p in libs]
    lines += [
        f"read_verilog {verilog}",
        "link_design gcd",
        f"read_spef {spef}",
        f"source {sdc}",
        f"report_wns -digits 4",
        f"report_tns -digits 4",
        f"report_checks -path_delay {path_delay} -format end -digits 4",
        "exit",
    ]
    tcl.write_text("\n".join(lines) + "\n")
    proc = subprocess.run([sta, "-no_splash", "-exit", str(tcl)], text=True, capture_output=True, timeout=180)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    wns = None
    tns = None
    m = re.search(r"wns(?:\s+max)?\s+(-?\d+(?:\.\d+)?)", text, re.I)
    if m:
        wns = float(m.group(1))
    m = re.search(r"tns(?:\s+max)?\s+(-?\d+(?:\.\d+)?)", text, re.I)
    if m:
        tns = float(m.group(1))
    slacks = [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?)\s+\((?:MET|VIOLATED)\)", text)]
    if path_delay == "min" and slacks:
        wns = min(slacks)
    elif wns is None and slacks:
        wns = min(slacks)
    return {
        "ok": proc.returncode == 0 and wns is not None,
        "exit_code": proc.returncode,
        "wns_ps": wns,
        "tns_ps": tns,
        "path_delay": path_delay,
        "n_paths": len(slacks),
        "stdout_tail": (proc.stdout or "")[-600:],
    }


def main() -> int:
    res = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    verilog = res / "6_final.v"
    spef = res / "6_final.spef"
    sdc = res / "6_final.sdc"
    if not (verilog.is_file() and spef.is_file() and sdc.is_file()):
        print(f"FAIL missing finish artifacts under {res}", file=sys.stderr)
        return 1
    setup = _sta_wns(verilog, spef, sdc, [ORFS / n for n in CORNER_LIBS["WC"]], "max")
    hold = _sta_wns(verilog, spef, sdc, [ORFS / n for n in CORNER_LIBS["BC"]], "min")
    payload = {
        "ok": bool(setup.get("ok") and hold.get("ok")),
        "surface": "lab",
        "platform": "asap7",
        "kind": "mmmc_pair",
        "product_win": False,
        "comparable_to_gold_ir": False,
        "netlist": str(verilog),
        "spef": str(spef),
        "sdc": str(sdc),
        "setup": {"corner": "WC", "lib": "SS", "volt": 0.63, "temp_c": 100, **setup},
        "hold": {"corner": "BC", "lib": "FF", "volt": 0.77, "temp_c": 25, **hold},
        "leftover": {
            "mmmc": "two serial OpenSTA runs, not a single MMMC session",
            "smoke_sdc": "SDC period is the cook SDC, not a 310 ps gold",
        },
        "note": (
            "Hammer-style setup WC + hold BC on one netlist. "
            "Not a product win. Live metrics only — no gold stamp."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        "lab_asap7_mmmc setup_wns",
        setup.get("wns_ps"),
        "hold_wns",
        hold.get("wns_ps"),
        "ok",
        payload["ok"],
    )
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

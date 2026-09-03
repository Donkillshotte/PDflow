#!/usr/bin/env python3
"""FILL injection and unused-library filter stay honest."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn/scripts"))
from prepare_lvs_netlist import fillers_from_def, inject_fillers, prepare  # noqa: E402


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    def_text = """
COMPONENTS 2 ;
    - FILLER_0_1 FILLCELL_X32 + SOURCE DIST + PLACED ( 0 0 ) N ;
    - FILLER_0_1 FILLCELL_X32 + SOURCE DIST + PLACED ( 0 0 ) N ;
    - FILLER_0_2 FILLCELL_X1 + PLACED ( 1 0 ) N ;
END COMPONENTS
"""
    fills = fillers_from_def(def_text)
    check(fills == [("FILLER_0_1", "FILLCELL_X32"), ("FILLER_0_2", "FILLCELL_X1")], "DEF fillers unique")
    cdl = ".SUBCKT gcd clk\nX1 a z VDD VSS INV_X1\n.ENDS\n"
    out = inject_fillers(cdl, fills, "gcd")
    check("XFILLER_0_1 VDD VSS FILLCELL_X32" in out, "injected FILLCELL instance")
    check(out.count(".ENDS") == 1, "single .ENDS")

    flow = ROOT / "tools/OpenROAD-flow-scripts/flow"
    design = flow / "results/nangate45/gcd/flowlab/6_final.cdl"
    lib = flow / "platforms/nangate45/cdl/NangateOpenCellLibrary.cdl"
    deff = flow / "results/nangate45/gcd/flowlab/6_final.def"
    if design.is_file() and lib.is_file() and deff.is_file():
        dest = Path("/tmp/test_lvs_prep.cdl")
        info = prepare(design_cdl=design, library_cdl=lib, def_path=deff, top="gcd", out=dest)
        check(info["n_fillers"] > 100, f"real DEF has many fillers ({info['n_fillers']})")
        check(info["n_masters"] < 80, f"unused library cells dropped ({info['n_masters']})")
        text = dest.read_text()
        check(".SUBCKT TBUF_X1" not in text, "TBUF unused cell not in filtered CDL")
        check(".SUBCKT INV_X1" in text, "INV_X1 kept")
    print("ALL test_prepare_lvs PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

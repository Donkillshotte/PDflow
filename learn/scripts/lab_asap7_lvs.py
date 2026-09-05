#!/usr/bin/env python3
"""Leftover-named ASAP7 cell-vs-CDL check. Not Calibre. Not a product win.

Compares GDS instance masters (KLayout) to .SUBCKT names in the fetched
7.5T CDL. Expect <100%. Do not stamp .lvs.ok. Do not restamp 45.298.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CDL_DIR = ROOT / "learn" / "lab" / "asap7" / "cdl"
OUT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_lvs.json"
DEFAULT_GDS = (
    ROOT
    / "tools/OpenROAD-flow-scripts/flow/results/asap7/gcd"
    / "lab_asap7_gcd_tc_rvt_nldm_7p5_480ps"
    / "6_final.gds"
)


def _subckts(cdl: Path) -> set[str]:
    names: set[str] = set()
    text = cdl.read_text(errors="replace")
    for m in re.finditer(r"(?im)^\s*\.SUBCKT\s+(\S+)", text):
        names.add(m.group(1))
    return names


def _gds_cells(gds: Path) -> tuple[str | None, set[str]]:
    klayout = shutil.which("klayout")
    if not klayout:
        return None, set()
    script = Path("/tmp/lab_asap7_gds_cells.py")
    script.write_text(
        "import pya\n"
        "ly = pya.Layout()\n"
        f"ly.read({str(gds)!r})\n"
        "top = ly.top_cell()\n"
        'print("TOP", top.name if top else "")\n'
        "seen = set()\n"
        "if top:\n"
        "    for inst in top.each_inst():\n"
        "        seen.add(inst.cell.name)\n"
        "for name in sorted(seen):\n"
        '    print("CELL", name)\n'
    )
    proc = subprocess.run(
        [klayout, "-b", "-zz", "-r", str(script)],
        text=True,
        capture_output=True,
        timeout=120,
    )
    top = None
    cells: set[str] = set()
    for line in (proc.stdout or "").splitlines():
        if line.startswith("TOP "):
            top = line[4:].strip() or None
        elif line.startswith("CELL "):
            cells.add(line[5:].strip())
    return top, cells


def _norm(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", name).upper()


def main() -> int:
    gds = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GDS
    cdl_paths = sorted(CDL_DIR.glob("asap7sc7p5t_28_*.cdl"))
    sub = set()
    for p in cdl_paths:
        sub |= _subckts(p)
    top, cells = _gds_cells(gds)
    # Skip filler / tap / decap noise in the coverage numerator? Keep all,
    # but report filler separately. Leftover-named, not a gold.
    fillers = {c for c in cells if c.upper().startswith(("FILL", "TAP", "DECAP"))}
    logic = cells - fillers
    hit = logic & sub
    pct = (100.0 * len(hit) / len(logic)) if logic else 0.0
    payload = {
        "ok": gds.is_file() and bool(sub) and bool(cells),
        "surface": "lab",
        "platform": "asap7",
        "kind": "leftover_named_lvs",
        "calibre": False,
        "netgen": shutil.which("netgen") is not None or shutil.which("netgen-lvs") is not None,
        "product_win": False,
        "comparable_to_gold_ir": False,
        "gds": str(gds) if gds.is_file() else None,
        "top": top,
        "cdl_files": [str(p) for p in cdl_paths],
        "n_cdl_subckt": len(sub),
        "n_gds_cells": len(cells),
        "n_logic": len(logic),
        "n_filler": len(fillers),
        "n_matched": len(hit),
        "match_pct": round(pct, 1),
        "lvs_closed": False,
        "leftover": {
            "calibre": "ASU tarball + Calibre 2017.3 not in this image",
            "deck": "no ASAP7 .lylvs in the ORFS slim pack",
            "expect": "<100% device match (vibeic ~76% on RVT)",
            "stamp": "never write .lvs.ok for ASAP7",
        },
        "note": (
            "Leftover-named cell-vs-CDL. Not Calibre. Not a product win. "
            "Live metrics only — no gold stamp."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"lab_asap7_lvs ok={payload['ok']} match={payload['n_matched']}/"
        f"{payload['n_logic']} ({payload['match_pct']}%) calibre=no"
    )
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

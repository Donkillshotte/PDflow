#!/usr/bin/env python3
"""Deeper educational LVS: filter unused CDL + VTL tolerances + optional black-box.

Does not write .lvs.ok. Transistor compare stays FAIL unless KLayout prints
a real match. Black-box (blank_circuit) is a separately labeled check.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "learn" / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn" / "scripts"))
from filter_lvs_cdl import filter_library, used_masters  # noqa: E402

FLOW = _ROOT / "tools/OpenROAD-flow-scripts/flow"
LYLVS = _ROOT / "learn/platforms/nangate45/lvs/FreePDK45.lylvs"
LIB_CDL = FLOW / "platforms/nangate45/cdl/NangateOpenCellLibrary.cdl"


def _variant() -> str:
    return os.environ.get("FLOW_VARIANT", "flowlab")


def _res(variant: str) -> Path:
    return FLOW / "results/nangate45/gcd" / variant


def _patch_vtl_tolerances(xml: str) -> str:
    repl = {
        "PMOS_LVT": "PMOS_VTL",
        "PMOS_GVT": "PMOS_VTG",
        "PMOS_HVT": "PMOS_VTH",
        "NMOS_LVT": "NMOS_VTL",
        "NMOS_GVT": "NMOS_VTG",
        "NMOS_HVT": "NMOS_VTH",
    }
    for old, new in repl.items():
        xml = xml.replace(f'tolerance("{old}"', f'tolerance("{new}"')
    return xml


def _inject_blank(xml: str, cells: list[str]) -> str:
    calls = "\n".join(f'blank_circuit("{c}")' for c in cells)
    needle = "if ! compare"
    if needle not in xml:
        raise RuntimeError("cannot find compare hook in lylvs")
    return xml.replace(needle, calls + "\n\nif ! compare", 1)


def _write_runset(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _klayout() -> str:
    for name in ("klayout",):
        p = shutil.which(name)
        if p:
            return p
    sh = FLOW / "util/klayout.sh"
    if sh.is_file():
        return str(sh)
    raise FileNotFoundError("klayout not on PATH")


def run_one(gds: Path, cdl: Path, runset: Path, report: Path, log: Path) -> dict:
    report.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _klayout(),
        "-b",
        "-rd",
        f"in_gds={gds}",
        "-rd",
        f"cdl_file={cdl}",
        "-rd",
        f"report_file={report}",
        "-r",
        str(runset),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    log.write_text(text)
    match = bool(re.search(r"CONGRATULATIONS! Netlists match", text))
    mismatch = bool(re.search(r"Netlists don't match", text))
    flatten = [ln.strip() for ln in text.splitlines() if "Flatten schematic circuit" in ln]
    return {
        "rc": proc.returncode,
        "match": match and not mismatch,
        "mismatch": mismatch,
        "flatten_no_layout": flatten[:20],
        "n_flatten": len(flatten),
        "log": str(log),
        "lvsdb": str(report),
        "tail": text.splitlines()[-12:],
    }


def main() -> int:
    variant = _variant()
    res = _res(variant)
    gds = res / "6_final.gds"
    design_cdl = res / "6_final.cdl"
    if not gds.is_file() or not design_cdl.is_file():
        print("missing GDS or design CDL — run finish first", file=sys.stderr)
        return 2
    if not LYLVS.is_file() or not LIB_CDL.is_file():
        print("missing lylvs or library CDL", file=sys.stderr)
        return 2

    keep = used_masters(design_cdl.read_text(errors="replace"))
    keep |= {
        "FILLCELL_X1",
        "FILLCELL_X2",
        "FILLCELL_X4",
        "FILLCELL_X8",
        "FILLCELL_X16",
        "FILLCELL_X32",
        "TAPCELL_X1",
    }
    filtered = design_cdl.read_text(errors="replace").rstrip() + "\n" + filter_library(
        LIB_CDL.read_text(errors="replace"), keep
    )
    obj = FLOW / "objects/nangate45/gcd" / variant
    obj.mkdir(parents=True, exist_ok=True)
    filt_cdl = obj / "6_final_deep_filtered.cdl"
    filt_cdl.write_text(filtered)
    print("LVS_DEEP keep", len(keep), "masters")

    base_xml = _patch_vtl_tolerances(LYLVS.read_text())
    trans_rs = obj / "FreePDK45_vtl.lylvs"
    box_rs = obj / "FreePDK45_blackbox.lylvs"
    _write_runset(base_xml, trans_rs)
    _write_runset(_inject_blank(base_xml, sorted(keep)), box_rs)

    deep_dir = res / "lvs_deep"
    trans = run_one(
        gds,
        filt_cdl,
        trans_rs,
        deep_dir / "transistor.lvsdb",
        _ROOT / "learn/sim/reports" / f"lvs_deep_transistor_{variant}.log",
    )
    box = run_one(
        gds,
        filt_cdl,
        box_rs,
        deep_dir / "blackbox.lvsdb",
        _ROOT / "learn/sim/reports" / f"lvs_deep_blackbox_{variant}.log",
    )

    stamp = res / ".lvs.ok"
    transistor_ok = bool(trans["match"])
    # Never stamp a black-box-only result as transistor LVS.
    if transistor_ok:
        stamp.write_text("deep transistor match\n")
    else:
        if stamp.exists():
            stamp.unlink()

    report = {
        "ok": False,  # signoff pillar stays fail unless transistor matches
        "kind": "lvs_deep",
        "status": "READY" if transistor_ok else "FAIL",
        "transistor": {**trans, "ok": transistor_ok},
        "blackbox": {**box, "ok": bool(box["match"]), "label": "connectivity-only blank_circuit"},
        "filtered_masters": sorted(keep),
        "n_filtered_masters": len(keep),
        "vtl_tolerances": True,
        "educational_note": (
            "Filtered unused library SUBCKTs and renamed device tolerances to "
            "NMOS_VTL/PMOS_VTL. Black-box is connectivity-only, not transistor LVS. "
            "Do not treat black-box PASS as tapeout LVS."
        ),
        "summary": (
            f"LVS deep transistor={'PASS' if transistor_ok else 'FAIL'} · "
            f"blackbox={'PASS' if box['match'] else 'FAIL'} · "
            f"filtered {len(keep)} masters · unused flatten {trans['n_flatten']}"
        ),
    }
    # Signoff ok only on real transistor match.
    report["ok"] = transistor_ok
    out = _ROOT / "learn/sim/reports" / f"lvs_deep_{variant}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(report["summary"])
    print("WROTE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

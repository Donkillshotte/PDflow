#!/usr/bin/env python3
"""Deeper educational LVS: filtered CDL + FILL from DEF + well→VDD/VSS.

Does not write .lvs.ok unless KLayout prints a real transistor match.
Black-box (blank_circuit on all used masters) is a separately labeled check.
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
from prepare_lvs_netlist import prepare  # noqa: E402

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
    p = shutil.which("klayout")
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
    flatten_sch = [ln.strip() for ln in text.splitlines() if "Flatten schematic circuit" in ln]
    flatten_lay = [ln.strip() for ln in text.splitlines() if "Flatten layout cell" in ln]
    return {
        "rc": proc.returncode,
        "match": match and not mismatch,
        "mismatch": mismatch,
        "flatten_no_layout": flatten_sch[:20],
        "flatten_no_schematic": flatten_lay[:20],
        "n_flatten": len(flatten_sch),
        "n_flatten_layout": len(flatten_lay),
        "log": str(log),
        "lvsdb": str(report),
        "tail": text.splitlines()[-16:],
    }


def main() -> int:
    variant = _variant()
    res = _res(variant)
    gds = res / "6_final.gds"
    design_cdl = res / "6_final.cdl"
    def_path = res / "6_final.def"
    if not gds.is_file() or not design_cdl.is_file():
        print("missing GDS or design CDL — run finish first", file=sys.stderr)
        return 2
    if not LYLVS.is_file() or not LIB_CDL.is_file():
        print("missing lylvs or library CDL", file=sys.stderr)
        return 2

    obj = FLOW / "objects/nangate45/gcd" / variant
    obj.mkdir(parents=True, exist_ok=True)
    filt_cdl = obj / "6_final_deep_filtered.cdl"
    prep = prepare(
        design_cdl=design_cdl,
        library_cdl=LIB_CDL,
        def_path=def_path if def_path.is_file() else None,
        top="gcd",
        out=filt_cdl,
    )
    print("LVS_DEEP keep", prep["n_masters"], "masters · fillers", prep["n_fillers"])

    base_xml = _patch_vtl_tolerances(LYLVS.read_text())
    trans_rs = obj / "FreePDK45_vtl.lylvs"
    box_rs = obj / "FreePDK45_blackbox.lylvs"
    _write_runset(base_xml, trans_rs)
    _write_runset(_inject_blank(base_xml, list(prep["masters"])), box_rs)

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
    if transistor_ok:
        stamp.write_text("deep transistor match\n")
    elif stamp.exists():
        stamp.unlink()

    report = {
        "ok": transistor_ok,
        "kind": "lvs_deep",
        "status": "READY" if transistor_ok else "FAIL",
        "transistor": {**trans, "ok": transistor_ok},
        "blackbox": {**box, "ok": bool(box["match"]), "label": "connectivity-only blank_circuit"},
        "filtered_masters": prep["masters"],
        "n_filtered_masters": prep["n_masters"],
        "n_fillers": prep["n_fillers"],
        "vtl_tolerances": True,
        "well_to_rails": True,
        "fill_from_def": True,
        "educational_note": (
            "Filtered unused library SUBCKTs, mapped wells to VDD/VSS, "
            "and injected FILLCELL instances from the DEF. "
            "Black-box is connectivity-only, not transistor LVS."
        ),
        "summary": (
            f"LVS deep transistor={'PASS' if transistor_ok else 'FAIL'} · "
            f"blackbox={'PASS' if box['match'] else 'FAIL'} · "
            f"filtered {prep['n_masters']} masters · fillers {prep['n_fillers']} · "
            f"unused flatten {trans['n_flatten']}"
        ),
    }
    out = _ROOT / "learn/sim/reports" / f"lvs_deep_{variant}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(report["summary"])
    print("WROTE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

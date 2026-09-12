#!/usr/bin/env python3
"""ASAP7 cell-vs-CDL check. Not Calibre and not a product result.

Compares GDS instance masters (KLayout) to .SUBCKT names in the fetched
7.5T CDL. Do not stamp `.lvs.ok`; report the current coverage and gaps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from dse.asap7_lab import LabAsap7Refuse, normalize_lab_variant, safe_result_dir

ROOT = Path(__file__).resolve().parents[2]
CDL_DIR = ROOT / "learn" / "lab" / "asap7" / "cdl"
OUT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_lvs.json"
DEFAULT_VARIANT = "lab_asap7_gcd_tc_rvt_nldm_7p5_480ps"


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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Leftover-named ASAP7 cell-vs-CDL. Not Calibre.")
    p.add_argument("gds", nargs="?", default="")
    p.add_argument("--variant", default="")
    args = p.parse_args(argv)
    variant = normalize_lab_variant(args.variant or DEFAULT_VARIANT)
    if args.gds:
        gds = Path(args.gds)
        if gds.parent.name.startswith("lab_asap7_"):
            variant = normalize_lab_variant(gds.parent.name)
    else:
        gds = safe_result_dir(variant, ROOT) / "6_final.gds"
    cdl_paths = sorted(CDL_DIR.glob("asap7sc7p5t_28_*.cdl"))
    if not cdl_paths:
        payload = {
            "ok": False,
            "status": "blocked",
            "legacy_status": "GAP",
            "tool_status": "blocked",
            "surface": "lab",
            "platform": "asap7",
            "track": "asap7",
            "mesh_id": "asap7_chip_tier_b",
            "topology": "fs",
            "oracle": "klayout_community",
            "tool_id": "klayout_community",
            "license_class": "GPL-2.0-or-later",
            "honesty": "GAP",
            "honesty_reason": "The public ASAP7 CDL input is not fetched; LVS cannot run.",
            "ok_claim": False,
            "kind": "leftover_named_lvs",
            "calibre": False,
            "product_win": False,
            "productWin": False,
            "win_eligible": False,
            "comparable_to_gold_ir": False,
            "comparison_scope": "independent ASAP7 LVS run",
            "variant": variant,
            "gds": str(gds) if gds.is_file() else None,
            "lvs_closed": False,
            "match_pct": 0,
            "leftover": {
                "calibre": "ASU tarball + Calibre 2017.3 not in this image",
                "fetch": "learn/scripts/fetch_asap7_libextras.sh",
            },
            "leftovers": [
                {"id": "cdl_missing", "message": "Public ASAP7 CDL is not available in this run."},
                {"id": "calibre_missing", "message": "No Calibre LVS deck/binary is available."},
            ],
            "pillars": {
                "lvs": {
                    "status": "blocked",
                    "honesty": "GAP",
                    "honesty_reason": "CDL input is missing.",
                    "leftovers": [{"id": "cdl_missing", "message": "Public ASAP7 CDL is not available."}],
                },
                "thermal": {
                    "status": "not_run",
                    "honesty": "GAP",
                    "honesty_reason": "Thermal is not part of the LVS check.",
                    "leftovers": [{"id": "thermal_not_run", "message": "No thermal model ran."}],
                },
            },
            "signoff_all": {"ok": False, "reason": "LVS GAP is not signoff."},
            "note": "CDL not fetched. Cell-vs-CDL GAP. Not Calibre. Not a product win.",
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2) + "\n")
        print("lab_asap7_lvs GAP CDL not fetched", flush=True)
        return 0
    sub = set()
    for p in cdl_paths:
        sub |= _subckts(p)
    top, cells = _gds_cells(gds)
    # Skip filler / tap / decap noise in the coverage numerator? Keep all,
    # but report filler separately. It is a live observation.
    fillers = {c for c in cells if c.upper().startswith(("FILL", "TAP", "DECAP"))}
    logic = cells - fillers
    hit = logic & sub
    pct = (100.0 * len(hit) / len(logic)) if logic else 0.0
    lvs_ok = gds.is_file() and bool(sub) and bool(cells)
    legacy_status = "ran"
    status = "pass" if lvs_ok else "blocked"
    honesty = "PARTIAL" if lvs_ok else "GAP"
    payload = {
        "ok": lvs_ok,
        "status": status,
        "legacy_status": legacy_status,
        "tool_status": status,
        "surface": "lab",
        "platform": "asap7",
        "track": "asap7",
        "mesh_id": "asap7_chip_tier_b",
        "topology": "fs",
        "oracle": "klayout_community",
        "tool_id": "klayout_community",
        "license_class": "GPL-2.0-or-later",
        "honesty": honesty,
        "honesty_reason": (
            "Community cell-vs-CDL coverage; not Calibre or foundry LVS."
            if lvs_ok
            else "LVS could not establish a complete current-run cell-vs-CDL input set."
        ),
        "ok_claim": False,
        "kind": "leftover_named_lvs",
        "calibre": False,
        "netgen": shutil.which("netgen") is not None or shutil.which("netgen-lvs") is not None,
        "product_win": False,
        "productWin": False,
        "win_eligible": False,
        "comparable_to_gold_ir": False,
        "comparison_scope": "independent ASAP7 LVS run",
        "variant": variant,
        "gds": str(gds) if gds.is_file() else None,
        "gds_sha256": _sha256(gds) if gds.is_file() else None,
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
        "leftovers": [
            {"id": "calibre_missing", "message": "No Calibre LVS deck/binary is available."},
            {"id": "community_coverage", "message": "Cell-vs-CDL coverage is not a foundry LVS claim."},
        ],
        "pillars": {
            "lvs": {
                "status": status,
                "honesty": honesty,
                "honesty_reason": "Community cell-vs-CDL coverage; not Calibre.",
                "leftovers": [{"id": "calibre_missing", "message": "No Calibre LVS deck/binary is available."}],
            },
            "thermal": {
                "status": "not_run",
                "honesty": "GAP",
                "honesty_reason": "Thermal is not part of the LVS check.",
                "leftovers": [{"id": "thermal_not_run", "message": "No thermal model ran."}],
            },
        },
        "signoff_all": {"ok": False, "reason": "Community LVS is leftover evidence, not signoff."},
        "note": (
            "Cell-vs-CDL. Not Calibre. Not a product win. "
            "Live metrics only."
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

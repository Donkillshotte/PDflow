#!/usr/bin/env python3
"""ASAP7 community KLayout DRC. Not Calibre. Not a product win.

Runs platforms/asap7/drc/asap7.lydrc (laurentc2). Leftover-named count.
Never writes .drc.ok. Never restamps gold Dynamic IR 45.298 mV.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from dse.asap7_lab import LabAsap7Refuse, result_dir_for_variant

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "tools/OpenROAD-flow-scripts/flow/platforms/asap7/drc/asap7.lydrc"
OUT = ROOT / "learn/sim/reports/lab_asap7_drc.json"
DEFAULT_VARIANT = "lab_asap7_gcd_tc_rvt_nldm_7p5"


def _gds_for(variant: str) -> Path:
    folder = result_dir_for_variant(variant, ROOT)
    if folder is None:
        return ROOT / "tools/OpenROAD-flow-scripts/flow/results/asap7/gcd" / variant / "6_final.gds"
    return folder / "6_final.gds"


def _count_rules(report: Path) -> dict:
    text = report.read_text(errors="replace") if report.is_file() else ""
    rules: dict[str, int] = {}
    for m in re.finditer(r"(?im)^(?:DRC|rule)\s+(\S+).*?\b(\d+)\b", text):
        rules[m.group(1)] = int(m.group(2))
    items = len(re.findall(r"(?i)violation", text))
    if not rules and report.is_file() and report.suffix in {".lyrdb", ".xml"}:
        items = text.count("<item>")
    return {"n_items": items, "per_rule": rules, "bytes": report.stat().st_size if report.is_file() else 0}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Leftover-named ASAP7 KLayout DRC. Not Calibre.")
    p.add_argument("--variant", default=DEFAULT_VARIANT)
    p.add_argument("--gds", default="")
    args = p.parse_args(argv)
    variant = args.variant
    if not variant.startswith("lab_asap7_"):
        raise LabAsap7Refuse(f"REFUSED: DRC variant must start with lab_asap7_ ({variant})")
    gds = Path(args.gds) if args.gds else _gds_for(variant)
    klayout = shutil.which("klayout")
    report = ROOT / "learn/sim/reports" / f"lab_asap7_drc_{variant}.lyrdb"
    report.parent.mkdir(parents=True, exist_ok=True)
    ran = False
    exit_code = None
    if not gds.is_file():
        payload_status = "GAP"
        reason = f"GDS missing {gds}"
    elif not DECK.is_file():
        payload_status = "GAP"
        reason = f"deck missing {DECK}"
    elif not klayout:
        payload_status = "GAP"
        reason = "klayout not in PATH"
    else:
        proc = subprocess.run(
            [
                klayout,
                "-b",
                "-r",
                str(DECK),
                "-rd",
                f"in_gds={gds}",
                "-rd",
                f"report_file={report}",
            ],
            text=True,
            capture_output=True,
            timeout=300,
        )
        ran = True
        exit_code = proc.returncode
        payload_status = "ran" if proc.returncode == 0 else "fail"
        reason = (proc.stderr or "")[-400:]
    counts = _count_rules(report)
    payload = {
        "ok": ran and exit_code == 0,
        "status": payload_status,
        "surface": "lab",
        "platform": "asap7",
        "kind": "leftover_named_drc",
        "calibre": False,
        "deck": "community laurentc2 asap7.lydrc",
        "product_win": False,
        "comparable_to_gold_ir": False,
        "variant": variant,
        "gds": str(gds) if gds.is_file() else None,
        "report": str(report) if report.is_file() else None,
        "n_items": counts["n_items"],
        "per_rule": counts["per_rule"],
        "leftover": {
            "calibre": "ASU tarball + Calibre 2017.3 not in this image",
            "deck": "community KLayout; several via-width rules off; OFFGRID=false",
            "gate": "nonzero items are leftover-named, not a fail",
        },
        "reason": reason,
        "note": (
            "Community KLayout DRC. Not Calibre. Not a product win. "
            "Live metrics only — no gold stamp."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"lab_asap7_drc ok={payload['ok']} items={payload['n_items']} "
        f"calibre=no variant={variant}",
        flush=True,
    )
    # Nonzero DRC items do not fail the script. Only KLayout itself failing does.
    if payload_status == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

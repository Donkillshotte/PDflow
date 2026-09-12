#!/usr/bin/env python3
"""ASAP7 community KLayout DRC. Not Calibre. Not a product win.

Runs platforms/asap7/drc/asap7.lydrc (laurentc2). Leftover-named count.
Never writes .drc.ok. DRC results are scoped to the current ASAP7 run.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from dse.asap7_lab import LabAsap7Refuse, normalize_lab_variant, safe_result_dir

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "tools/OpenROAD-flow-scripts/flow/platforms/asap7/drc/asap7.lydrc"
OUT = ROOT / "learn/sim/reports/lab_asap7_drc.json"
DEFAULT_VARIANT = "lab_asap7_gcd_tc_rvt_nldm_7p5"


def _gds_for(variant: str) -> Path:
    return safe_result_dir(variant, ROOT) / "6_final.gds"


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
    variant = normalize_lab_variant(args.variant)
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
    klayout_ok = ran and exit_code == 0
    drc_clean = counts["n_items"] == 0
    legacy_status = payload_status
    status = "pass" if klayout_ok else "blocked"
    honesty = "PARTIAL" if ran else "GAP"
    payload = {
        "ok": klayout_ok and drc_clean,
        "klayout_ok": klayout_ok,
        "drc_clean": drc_clean,
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
            "Community KLayout rules are evidence only; Calibre/foundry DRC "
            "coverage is not present."
            if ran
            else "Community DRC did not run because a required input or tool is missing."
        ),
        "ok_claim": False,
        "kind": "leftover_named_drc",
        "calibre": False,
        "deck": "community laurentc2 asap7.lydrc",
        "product_win": False,
        "productWin": False,
        "win_eligible": False,
        "comparable_to_gold_ir": False,
        "comparison_scope": "independent ASAP7 DRC run",
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
        "leftovers": [
            {"id": "calibre_missing", "message": "No Calibre deck/binary is part of this community run."},
            {"id": "via_width_rules", "message": "Several via-width rules remain outside the community deck."},
        ],
        "pillars": {
            "drc": {
                "status": status,
                "honesty": honesty,
                "honesty_reason": "Community KLayout DRC; not Calibre.",
                "leftovers": [
                    {"id": "calibre_missing", "message": "No Calibre deck/binary is available."},
                ],
            },
            "thermal": {
                "status": "not_run",
                "honesty": "GAP",
                "honesty_reason": "Thermal is not part of the DRC check.",
                "leftovers": [{"id": "thermal_not_run", "message": "No thermal model ran."}],
            },
        },
        "signoff_all": {"ok": False, "reason": "Community DRC is leftover evidence, not signoff."},
        "note": (
            "Community KLayout DRC. Not Calibre. Not a product win. "
            "Live metrics only."
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
    if not klayout_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Write signoff_all JSON from existing pillar reports.

Does not re-run STA / DRC / LVS / power. Names LVS leftover and the
IR mesh ledger so a four-pillar PASS is not a leftover-free close.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"


def _load(name: str) -> dict | None:
    path = REPORTS / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def leftover_from_lvs(lvs: dict | None) -> dict | None:
    if not lvs:
        return None
    mc = int(lvs.get("must_connect") or 0)
    if mc <= 0:
        return None
    messages = ((lvs.get("artifact_parse") or {}).get("lvsdb") or {}).get("messages") or []
    cells = sorted(
        {
            m.group(1)
            for raw in messages
            if (m := re.search(r"circuit (\S+)", str(raw)))
        }
    )
    return {
        "must_connect": mc,
        "circuits": cells,
        "note": "Nangate split wells. Compare still matches. Do not hide.",
    }


def leftover_summary_suffix(leftover: dict | None) -> str:
    """Append leftover to a PASS line so a summary-only reader cannot hide it."""
    if not leftover:
        return ""
    cells = leftover.get("circuits") or []
    named = f" ({', '.join(cells)})" if cells else ""
    return f" · leftover must-connect {leftover['must_connect']}{named}"


def with_leftover_summary(summary: str | None, leftover: dict | None) -> str:
    text = str(summary or "")
    suffix = leftover_summary_suffix(leftover)
    if suffix and "leftover must-connect" not in text:
        return f"{text}{suffix}"
    return text


def build(variant: str = "flowlab") -> dict:
    pillars: dict[str, dict] = {}
    files = {
        "timing": f"sta_signoff_{variant}.json",
        "geometry": f"drc_signoff_{variant}.json",
        "equivalence": f"lvs_signoff_{variant}.json",
        "power": f"power_signoff_{variant}.json",
    }
    leftover = None
    ledger = None
    for kind, fname in files.items():
        report = _load(fname)
        if report is None:
            pillars[kind] = {"ok": False, "summary": "missing"}
            continue
        row = {"ok": report.get("ok"), "summary": report.get("summary")}
        if kind == "equivalence":
            leftover = leftover_from_lvs(report)
            if leftover:
                row["leftover"] = leftover
                row["summary"] = with_leftover_summary(row.get("summary"), leftover)
        if kind == "power":
            ledger = report.get("ir_mesh_ledger")
            if isinstance(ledger, dict):
                row["ir_mesh_ledger"] = {
                    "comparable": ledger.get("comparable"),
                    "n_meshes": len(ledger.get("meshes") or []),
                }
                if ledger.get("comparable") is False:
                    row["summary"] = f"{row['summary']} · IR meshes not comparable"
        pillars[kind] = row

    parts = [f"{k}:{'ok' if p.get('ok') else 'fail'}" for k, p in pillars.items()]
    if leftover:
        cells = ", ".join(leftover["circuits"]) or "Nangate cell"
        parts.append(f"leftover must-connect {leftover['must_connect']} ({cells})")
    if isinstance(ledger, dict) and ledger.get("comparable") is False:
        parts.append("IR meshes not comparable")

    return {
        "kind": "signoff_all",
        "variant": variant,
        "pillars": pillars,
        "ok": all(p.get("ok") for p in pillars.values()),
        "summary": " · ".join(parts),
        "leftover": leftover,
        "ir_mesh_ledger": (
            {
                "comparable": ledger.get("comparable"),
                "n_meshes": len(ledger.get("meshes") or []),
            }
            if isinstance(ledger, dict)
            else None
        ),
    }


def stamp(variant: str = "flowlab") -> dict:
    blob = build(variant)
    out = REPORTS / f"signoff_all_{variant}.json"
    out.write_text(json.dumps(blob, indent=2) + "\n")
    leftover = blob.get("leftover")
    if leftover:
        lvs_path = REPORTS / f"lvs_signoff_{variant}.json"
        if lvs_path.is_file():
            lvs = json.loads(lvs_path.read_text())
            changed = False
            if lvs.get("leftover") != leftover:
                lvs["leftover"] = leftover
                changed = True
            named = with_leftover_summary(lvs.get("summary"), leftover)
            if named != lvs.get("summary"):
                lvs["summary"] = named
                changed = True
            if changed:
                lvs_path.write_text(json.dumps(lvs, indent=2) + "\n")
    return blob


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", default="flowlab")
    ap.add_argument("--stamp", action="store_true")
    args = ap.parse_args()
    blob = stamp(args.variant) if args.stamp else build(args.variant)
    print(blob["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

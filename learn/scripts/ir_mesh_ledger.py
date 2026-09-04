#!/usr/bin/env python3
"""Name the IR / EM meshes that power_signoff must not mix.

Gold Dynamic IR 45.298 mV is a locked reference_run. Chip PDN, current_run
I(t), vyges-em-ir, and system PDN are other meshes. This script only
reads existing reports. It does not restamp gold and does not invent
an emlimit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"
GOLD_MV = 45.298


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _mv(value, scale: float = 1.0) -> float | None:
    if value is None:
        return None
    try:
        return float(value) * scale
    except (TypeError, ValueError):
        return None


def build_ledger(variant: str = "flowlab") -> dict:
    gold_path = REPORTS / f"dynamic_ir_{variant}.json"
    gold = _load(gold_path)
    if gold is None and variant != "flowlab":
        gold_path = REPORTS / "dynamic_ir_flowlab.json"
        gold = _load(gold_path)
    current = _load(REPORTS / f"dynamic_ir_{variant}_direct.json")
    chip = _load(REPORTS / f"pdn_chip_ir_{variant}.json")
    system = _load(REPORTS / f"system_pdn_{variant}.json")
    vyges = _load(REPORTS / f"vyges_em_ir_{variant}.json")

    meshes: list[dict] = []

    gold_mv = _mv((gold or {}).get("worst_droop_mv"))
    if gold and gold_mv is not None:
        meshes.append(
            {
                "id": "gold_dynamic_ir",
                "mesh": "gold Dynamic IR reference_run",
                "report": str(gold_path.relative_to(ROOT)).replace("learn/", "", 1)
                if str(gold_path).startswith(str(ROOT / "learn"))
                else f"sim/reports/{gold_path.name}",
                "static_mv": None,
                "dynamic_mv": gold_mv,
                "gold": gold.get("gold") is True,
                "em_checked": None,
                "comparable_to": [],
                "note": "LOCKED. Not current_run. Do not restamp.",
            }
        )

    cur_mv = _mv((current or {}).get("worst_droop_mv"))
    if cur_mv is None and current:
        cur_mv = _mv(((current.get("dynamic") or {}).get("worst_droop")), 1e3)
    cur_static = _mv(((current or {}).get("static") or {}).get("worst_ir_mv"))
    if cur_static is None and current:
        cur_static = _mv((current.get("static") or {}).get("worst_ir"), 1e3)
    if current and cur_mv is not None:
        meshes.append(
            {
                "id": "current_run_dynamic_ir",
                "mesh": "current_run Dynamic IR I(t)",
                "report": f"sim/reports/dynamic_ir_{variant}_direct.json",
                "static_mv": cur_static,
                "dynamic_mv": cur_mv,
                "gold": False,
                "em_checked": None,
                "comparable_to": [],
                "note": "I(t) mesh. Not gold 45.298. Not chip PDN.",
            }
        )

    if chip:
        static_mv = _mv((chip.get("static") or {}).get("worst_ir"), 1e3)
        tran_mv = _mv((chip.get("transient") or {}).get("worst_droop"), 1e3)
        meshes.append(
            {
                "id": "chip_pdn",
                "mesh": "write_pg_spice chip PDN",
                "report": f"sim/reports/pdn_chip_ir_{variant}.json",
                "static_mv": static_mv,
                "dynamic_mv": tran_mv,
                "gold": False,
                "em_checked": None,
                "comparable_to": [],
                "note": "Signoff power pillar uses this chip static + transient.",
            }
        )

    if vyges:
        v = vyges.get("vyges") or {}
        meshes.append(
            {
                "id": "vyges_em_ir",
                "mesh": "vyges-em-ir (different mesh)",
                "report": f"sim/reports/vyges_em_ir_{variant}.json",
                "static_mv": _mv((v.get("worst_ir") or {}).get("drop"), 1e3),
                "dynamic_mv": _mv((v.get("dynamic") or {}).get("drop"), 1e3),
                "gold": False,
                "em_checked": int(v.get("em_checked") or 0),
                "comparable_to": [],
                "note": "No foundry emlimit. em_checked stays 0.",
            }
        )

    if system:
        meshes.append(
            {
                "id": "system_pdn",
                "mesh": "lumped VRM→board→pkg→die",
                "report": f"sim/reports/system_pdn_{variant}.json",
                "static_mv": None,
                "dynamic_mv": _mv((system.get("transient") or {}).get("droop_mv")),
                "gold": False,
                "em_checked": None,
                "zmax_mohm": _mv((system.get("impedance") or {}).get("z_max_mohm")),
                "comparable_to": [],
                "note": "Package/board ladder. Not on-die mesh IR.",
            }
        )

    return {
        "ok": True,
        "variant": variant,
        "comparable": False,
        "note": (
            "These droop numbers are not interchangeable. "
            "Gold stays 45.298 mV. EM has no emlimit."
        ),
        "meshes": meshes,
    }


def stamp(variant: str = "flowlab") -> dict:
    ledger = build_ledger(variant)
    out = REPORTS / f"power_signoff_{variant}.json"
    blob = _load(out) or {
        "kind": "power_signoff",
        "variant": variant,
        "ok": None,
        "summary": "power_signoff report missing — ledger only",
    }
    blob["ir_mesh_ledger"] = ledger
    out.write_text(json.dumps(blob, indent=2) + "\n")
    return ledger


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", default="flowlab")
    ap.add_argument("--stamp", action="store_true", help="write ir_mesh_ledger into power_signoff JSON")
    args = ap.parse_args()
    ledger = stamp(args.variant) if args.stamp else build_ledger(args.variant)
    print(json.dumps(ledger, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

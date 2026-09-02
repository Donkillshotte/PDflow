#!/usr/bin/env python3
"""Launch compare: deltas are honest, gold ingest is not a product ΔIR."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from record_dse_launch import GOLD_MV, compare, snapshot_from_report  # noqa: E402


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    cook = snapshot_from_report(
        {
            "ok": True,
            "variant": "flowlab",
            "design_id": "gcd",
            "summary": "test cook",
            "n_candidates": 140,
            "n_f4": 60,
            "winning_ir_pdn_mv": 1.705,
            "winning_static_mv": 0.565,
            "ir_champ_amg_mv": 1.705,
            "ir_cell_champ_wns_ns": -0.288,
            "spent_s": 12.0,
        }
    )
    check(cook["role"] == "cook", "cook role")
    check(cook["n_candidates"] == 140, "candidate count")
    first = compare(cook, None)
    check(first["versus"] is None, "first launch has no previous")
    ingest = {
        "role": "ingest",
        "variant": "flowlab",
        "winning_ir_pdn_mv": GOLD_MV,
        "n_candidates": 1,
        "winning_static_mv": 17.5,
        "ir_cell_champ_wns_ns": 0.04,
        "spent_s": 0.0,
        "created_at": 1.0,
    }
    vs_gold = compare(cook, ingest)
    check(vs_gold["same_mesh"] is False, "ingest vs cook is not same mesh")
    check("45.298" in vs_gold["note"], "gold ingest called out in the note")
    check(abs((vs_gold["delta"]["winning_ir_pdn_mv"] or 0) - (1.705 - GOLD_MV)) < 1e-6, "ΔIR numeric")
    prev_cook = dict(cook)
    prev_cook["role"] = "cook"
    prev_cook["created_at"] = 2.0
    prev_cook["n_candidates"] = 100
    prev_cook["winning_ir_pdn_mv"] = 2.0
    vs_cook = compare(cook, prev_cook)
    check(vs_cook["same_mesh"] is True, "two cooks on flowlab share role")
    check(abs((vs_cook["delta"]["n_candidates"] or 0) - 40) < 1e-9, "Δ candidates")
    print("ALL test_record_dse_launch PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

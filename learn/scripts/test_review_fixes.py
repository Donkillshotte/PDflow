#!/usr/bin/env python3
"""Negative tests for static review fixes (variant guard, win_rule, fail-closed)."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from dse.asap7_lab import LabAsap7Refuse, normalize_lab_variant
from dse.win_rule import verdict


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> None:
    check(normalize_lab_variant("lab_asap7_gcd_tc_rvt_nldm_7p5_480ps").startswith("lab_asap7_"), "valid variant accepted")
    for bad in (
        "lab_asap7_../gcd",
        "lab_asap7_gcd/evil",
        "lab_asap7_gcd:evil",
        "flowlab",
        "nangate45/gcd/flowlab",
    ):
        try:
            normalize_lab_variant(bad)
        except LabAsap7Refuse:
            check(True, f"refuse {bad}")
        else:
            raise SystemExit(f"FAIL expected refuse for {bad}")

    base = SimpleNamespace(
        finish_wns_ns=0.0,
        stdcell_um2=100.0,
        power_w=1.0,
        leakage_w=0.1,
        ir_drop_v=0.05,
    )
    cand_win = SimpleNamespace(
        finish_wns_ns=0.01,
        stdcell_um2=89.0,
        power_w=0.9,
        leakage_w=0.09,
        ir_drop_v=0.045,
    )
    cand_missing = SimpleNamespace(
        finish_wns_ns=0.01,
        stdcell_um2=None,
        power_w=0.9,
        leakage_w=0.09,
        ir_drop_v=0.045,
    )
    check(verdict(cand_win, base) == "win", "complete metrics can win")
    check(verdict(cand_missing, base) == "incomplete", "missing area is incomplete not win")
    check(verdict(SimpleNamespace(finish_wns_ns=None), base) == "incomplete", "missing slack is incomplete")

    from lab_asap7_chip_pdn import complete_asap7_mesh_spice
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "mesh.sp"
        dst = Path(tmp) / "mesh_done.sp"
        src.write_text("R1 BPinNode_0 ITermNode_0 1\nR2 ITermNode_0 n2 1\n")
        patch = complete_asap7_mesh_spice(src, dst, 0.7, 0.0)
        check(patch.get("patched") is False, "zero ITerm load refused when ITerm nodes exist")
        check("finish power missing" in str(patch.get("reason")), "zero load reason is explicit")

    print("PASS test_review_fixes")


if __name__ == "__main__":
    main()

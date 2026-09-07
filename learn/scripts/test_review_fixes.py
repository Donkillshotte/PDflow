#!/usr/bin/env python3
"""Lab-only negative tests: normalize_lab_variant + chip_pdn fail-closed.

No win_rule / product campaign asserts (those stay out of this lab split).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from dse.asap7_lab import LabAsap7Refuse, normalize_lab_variant
from lab_asap7_chip_pdn import complete_asap7_mesh_spice


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> None:
    check(
        normalize_lab_variant("lab_asap7_gcd_tc_rvt_nldm_7p5_480ps").startswith("lab_asap7_"),
        "valid variant accepted",
    )
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

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "mesh.sp"
        dst = Path(tmp) / "mesh_done.sp"
        src.write_text("R1 BPinNode_0 ITermNode_0 1\nR2 ITermNode_0 n2 1\n")
        patch = complete_asap7_mesh_spice(src, dst, 0.7, 0.0)
        check(patch.get("patched") is False, "zero ITerm load refused when ITerm nodes exist")
        check("finish power missing" in str(patch.get("reason")), "zero load reason is explicit")

    print("PASS test_review_fixes (lab-only)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Physics validator: gold untouched, STA IR reconstructs, real-slot IR labeled."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from validate_lab_physics import GOLD_MV, validate  # noqa: E402


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    rep = validate()
    by = {c["id"]: c for c in rep["checks"]}
    check(rep["ok"] is True, "no FAIL checks")
    check(by["gold_sentinel"]["ok"], "gold 45.298")
    check(abs(float(by["gold_sentinel"]["value"]) - GOLD_MV) < 0.02, "gold value")
    check(by["current_run_droop"]["ok"], "current_run ~6.075")
    check(by["gold_vs_current_split"]["ok"], "gold and current stay apart")
    check(by["sta_ir_path"]["ok"], "STA IR 18/18")
    check(by["sta_ir_reconstruct"]["ok"], "per-gate sum = slack − slack_ir")
    check(by["sta_ir_alpha_law"]["ok"], "α-law on joined gates")
    check(by["gcd_orfs_vs_dynamic"]["ok"], "ORFS static and TRAN same order on GCD")
    check(by["aes_not_gold"]["ok"], "AES is not gold")
    check(by["orfs_ir_ibex"]["status"] == "WATCH", "ibex 124 mV is WATCH not hidden")
    check(by["orfs_ir_aes"]["status"] == "WATCH", "aes ORFS 81 mV is WATCH")
    check(by["dse_winning_ir_not_gold"]["ok"], "DSE winning IR is not gold 45.298")
    check(by["dse_winning_static"]["ok"], "DSE winning static is rail-scale")
    check(by["dse_amg_vs_ras"]["ok"], "DSE AMG and RAS agree")
    reports = _SCRIPTS.parents[1] / "learn/sim/reports"
    for key, fname in (
        ("sta_signoff", "sta_signoff_flowlab.json"),
        ("vectorless", "vectorless_flowlab.json"),
        ("chip_pdn", "pdn_chip_ir_flowlab.json"),
        ("system_pdn", "system_pdn_flowlab.json"),
        ("thermal", "thermal_signoff_flowlab.json"),
    ):
        present = (reports / fname).is_file()
        st = by[f"artifact_{key}"]["status"]
        if present:
            check(st == "READY" and by[f"artifact_{key}"]["ok"], f"{key} on disk is READY")
        else:
            check(st == "GAP", f"missing {key} stays GAP")
    missing = [
        fname
        for fname in (
            "vectorless_flowlab.json",
            "pdn_chip_ir_flowlab.json",
            "system_pdn_flowlab.json",
            "thermal_signoff_flowlab.json",
        )
        if not (reports / fname).is_file()
    ]
    if missing:
        check("GAP" in {c["status"] for c in rep["checks"]}, f"GAP remains for {missing}")
    gold = json.loads((_SCRIPTS.parents[1] / "learn/sim/reports/dynamic_ir_flowlab.json").read_text())
    check(gold.get("gold") is True, "gold file still gold")
    print("ALL test_lab_physics PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

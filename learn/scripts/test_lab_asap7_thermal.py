#!/usr/bin/env python3
"""Tests for the explicit ASAP7 thermal GAP contract."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lab_asap7_thermal import build_report, write_report


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL {message}")
    print(f"ok  {message}")


def main() -> int:
    report = build_report(variant="lab_asap7_gcd_tc_rvt_nldm_7p5", run_id="thermal-test")
    check(report["status"] == "not_run", "thermal tool status is not_run")
    check(report["honesty"] == "GAP", "thermal honesty is GAP")
    check(report["pillars"]["thermal"]["model_id"] is None, "thermal model is explicit null")
    check(report["pillars"]["thermal"]["powermap_kind"] is None, "powermap kind is explicit null")
    check(report["leftovers"], "thermal leftovers are named")
    check("expected_mv" not in json.dumps(report) and "gold_mv" not in json.dumps(report), "no voltage oracle")
    check(report["product_win"] is False and report["productWin"] is False, "thermal Product firewall")
    with tempfile.TemporaryDirectory(prefix="pdflow-thermal-") as raw:
        path = write_report(Path(raw) / "lab_asap7_thermal.json", report)
        check(json.loads(path.read_text())["status"] == "not_run", "thermal report serializes")
    print("ALL test_lab_asap7_thermal PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

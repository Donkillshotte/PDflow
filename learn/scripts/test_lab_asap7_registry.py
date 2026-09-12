#!/usr/bin/env python3
"""Focused registry/comparison contract tests for the ASAP7 Lab lane."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lab_asap7_bspdn_proxy import ProxyContractError, build_report
from lab_asap7_registry import (
    build_registry_row,
    comparison_allowed,
    registry_errors,
    same_mesh,
    validate_registry_row,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL {message}")
    print(f"ok  {message}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pdflow-lab-registry-") as raw:
        report_path = Path(raw) / "proxy.json"
        report = build_report(
            variant="lab_asap7_gcd_tc_rvt_nldm_7p5",
            run_id="registry-test",
            output_path=report_path,
        )
        row = build_registry_row(report, report_path="learn/sim/reports/lab_asap7_bspdn_proxy.json")
        validate_registry_row(row)
        check(row["productWin"] is False and row["win_eligible"] is False, "T2 registry Product firewall")
        check(row["honesty"] == "PROXY" and row["status"] == "pass", "T3 registry dual axis")
        check(row["resultsDir"].startswith("tools/OpenROAD-flow-scripts/flow/results/asap7/"), "T7 pathGuard")

        left = {
            "mesh_id": "asap7_bspdn_proxy_m89",
            "mesh_fingerprint": "sha256:abc",
            "platform": "asap7",
            "design": "gcd",
            "nickname": "gcd",
            "topology": "proxy",
        }
        right = dict(left)
        check(same_mesh(left, right), "T5 same_mesh happy")
        right["mesh_fingerprint"] = None
        check(not same_mesh(left, right), "T6 same_mesh missing fingerprint")
        right = dict(left, mesh_fingerprint="sha256:abc", topology="fs")
        check(not comparison_allowed(left, right, strict=True), "T7 cross topology refused")
        candidate = dict(left, mesh_id="asap7_candidate_m89")
        check(not comparison_allowed(left, candidate, strict=True), "T8 candidate cross-family refused")
        nangate = dict(left, mesh_id="nangate_system_pdn", platform="nangate45")
        check(not comparison_allowed(left, nangate, strict=True), "T9 cross-PDK refused")

        broken = dict(row)
        broken["status"] = "PROXY"
        check(any("never PROXY" in error for error in registry_errors(broken)), "T14 PROXY cannot be status")
        broken = dict(row, track="asap7_bb")
        check(any("admit-capable" in error for error in registry_errors(broken)), "T27 ASAP7-BB EDU-only")
        broken = dict(row, productWin=True)
        check(any("productWin" in error for error in registry_errors(broken)), "T17 Product surface firewall")
        broken = dict(row, mesh_id="asap7_bspdn_chip")
        check(any("emit-forbidden" in error for error in registry_errors(broken)), "T21 chip mesh registry gate")

        with tempfile.TemporaryDirectory(prefix="pdflow-registry-output-") as out_raw:
            output = Path(out_raw) / "registry.json"
            output.write_text(json.dumps(row), encoding="utf-8")
            check(json.loads(output.read_text())["mesh_id"] == row["mesh_id"], "registry row serializes")

    print("ALL test_lab_asap7_registry PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

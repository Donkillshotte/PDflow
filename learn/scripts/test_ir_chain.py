#!/usr/bin/env python3
"""Dynamic, chip, package and EM reports remain distinct live artifacts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def load(name: str) -> dict:
    path = REPORTS / name
    check(path.is_file(), f"{name} exists")
    return json.loads(path.read_text())


def assert_proxy_evidence(report: dict, label: str) -> None:
    check(report.get("status") == "PROXY", f"{label} keeps proxy status explicit")
    check(report.get("ok") is False, f"{label} cannot be a signoff pass")
    check(report.get("execution_status") == "COMPLETED", f"{label} execution completed")
    check(report.get("evidence_status") == "PASS", f"{label} contains executable evidence")
    check(report.get("requirement_status") == "GAP", f"{label} requirement gap is explicit")
    check(report.get("signoff_status") == "PROXY", f"{label} signoff scope is proxy")
    check(report.get("product_signoff") is False, f"{label} cannot claim Product signoff")


def main() -> int:
    dynamic = load("dynamic_ir_flowlab_direct.json")
    assert_proxy_evidence(dynamic, "Dynamic IR")
    check(dynamic.get("comparison_scope") == "same-live-invocation", "Dynamic IR is current")
    check(float((dynamic.get("dynamic") or {}).get("worst_droop") or 0) > 0, "Dynamic IR droop is positive")
    check("comparison_scope" in dynamic, "Dynamic IR declares its live scope")

    chip = load("pdn_chip_ir_flowlab.json")
    assert_proxy_evidence(chip, "chip IR")
    check(float((chip.get("static") or {}).get("worst_ir") or 0) > 0, "chip static IR is positive")
    check(float((chip.get("transient") or {}).get("worst_droop") or 0) > 0, "chip transient IR is positive")

    system = load("system_pdn_flowlab.json")
    if system.get("status") == "GAP":
        check(system.get("ok") is False, "system PDN GAP is not a pass")
        reason = str(system.get("reason") or "").lower()
        check("ngspice" in reason or "xyce" in reason, "system PDN GAP names its missing engine")
    else:
        check(system.get("ok") is True, "system PDN report is ready")
        check(float((system.get("transient") or {}).get("droop_mv") or 0) > 0, "system droop is positive")

    power = load("power_signoff_flowlab.json")
    ledger = power.get("ir_mesh_ledger") or {}
    meshes = {row.get("id"): row for row in ledger.get("meshes") or []}
    check(set(("dynamic_ir", "chip_pdn", "system_pdn")) <= meshes.keys(), "ledger contains current meshes")
    check(all(not str(row.get("id", "")).startswith(("archived", "legacy", "fixed")) for row in meshes.values()), "ledger has no archived mesh")
    check(all(row.get("comparison_scope") for row in meshes.values()), "every mesh declares scope")
    check(meshes["dynamic_ir"].get("comparison_scope") == "same-live-extract", "same-extract scope is explicit")
    check(all(row.get("comparable_to") == [] for row in meshes.values()), "cross-mesh arithmetic is disabled")

    vyges = REPORTS / "vyges_em_ir_flowlab.json"
    if vyges.is_file():
        blob = json.loads(vyges.read_text())
        assert_proxy_evidence(blob, "EM report")
        drop = ((blob.get("vyges") or {}).get("worst_ir") or {}).get("drop")
        check(drop is not None and float(drop) > 0, "EM mesh has positive live drop")

    print("ALL test_ir_chain PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

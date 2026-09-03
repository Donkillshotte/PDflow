#!/usr/bin/env python3
"""Signoff reports must not fake a pass. Educational GAP stays GAP."""
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


def main() -> int:
    gold = load("dynamic_ir_flowlab.json")
    check(gold.get("gold") is True, "gold sentinel still gold")
    check(abs(float(gold["worst_droop_mv"]) - 45.298) < 0.02, "gold droop 45.298")

    lvs = load("lvs_signoff_flowlab.json")
    check(lvs.get("ok") is False, "LVS mismatch is fail")
    tail = ((lvs.get("artifact_parse") or {}).get("log") or {}).get("tail") or []
    check(any("Netlists don't match" in str(x) for x in tail), "LVS keeps KLayout mismatch")
    stamp = ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/.lvs.ok"
    check(not stamp.exists(), "failed LVS does not leave .lvs.ok")

    rdl = load("pkg_rdl_flowlab.json")
    check(rdl.get("ok") is False, "pkg_rdl is not a mock pass")
    check(rdl.get("status") == "GAP", "pkg_rdl status is GAP")
    check((rdl.get("rdl") or {}).get("executed") is False, "rdl_route was not executed")
    check((rdl.get("evaluation") or {}).get("ok") is False, "pkg_rdl evaluation.ok is false")

    bump = load("pkg_bump_flowlab.json")
    check(bump.get("ok") is True, "pkg_bump executed on mesh+config")

    pkg = load("pkg_signoff_flowlab.json")
    check(pkg.get("ok") is True, "pkg_signoff ok from bump + system PDN")
    rdl_step = (pkg.get("steps") or {}).get("pkg_rdl") or {}
    check(rdl_step.get("ok") is False, "pkg_signoff does not promote RDL GAP to pass")
    check("GAP" in str(pkg.get("summary")), "pkg_signoff summary labels RDL GAP")
    rdl_check = next(
        (c for c in (pkg.get("evaluation") or {}).get("checks") or [] if c.get("id") == "pkg_rdl"),
        None,
    )
    check(rdl_check is not None and rdl_check.get("ok") is False, "nested RDL check is fail")

    ph2 = load("signoff_phase2_flowlab.json")
    check(ph2.get("ok") is True, "phase 2 ok from thermal proxy + executable PKG")
    check((ph2.get("pillars") or {}).get("thermal", {}).get("ok") is True, "thermal proxy ok")

    sta_ir = load("sta_ir_aware_flowlab.json")
    check(sta_ir.get("ok") is True, "STA IR-aware report ok")

    signoff_all = load("signoff_all_flowlab.json")
    check(signoff_all.get("ok") is False, "signoff_all stays fail while LVS fails")
    print("ALL test_signoff_honesty PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

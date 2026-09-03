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
    check(rdl.get("ok") is True, "pkg_rdl executed dummy rdl_route")
    check(rdl.get("status") == "READY", "pkg_rdl status is READY")
    check((rdl.get("rdl") or {}).get("executed") is True, "rdl_route wrote sidecar wires")
    check((rdl.get("evaluation") or {}).get("ok") is True, "pkg_rdl evaluation.ok is true")
    note = str(rdl.get("educational_note") or "")
    check("not C4" in note or "dummy" in note.lower(), "pkg_rdl keeps dummy-not-C4 label")

    bump = load("pkg_bump_flowlab.json")
    check(bump.get("ok") is True, "pkg_bump executed on mesh+config")

    pkg = load("pkg_signoff_flowlab.json")
    check(pkg.get("ok") is True, "pkg_signoff ok from bump + system PDN")
    rdl_step = (pkg.get("steps") or {}).get("pkg_rdl") or {}
    check(rdl_step.get("ok") is True, "pkg_signoff records dummy rdl_route ok")
    rdl_check = next(
        (c for c in (pkg.get("evaluation") or {}).get("checks") or [] if c.get("id") == "pkg_rdl"),
        None,
    )
    check(rdl_check is not None and rdl_check.get("ok") is True, "nested RDL check is pass")

    ph2 = load("signoff_phase2_flowlab.json")
    check(ph2.get("ok") is True, "phase 2 ok from HotSpot + executable PKG")
    check((ph2.get("pillars") or {}).get("thermal", {}).get("ok") is True, "HotSpot thermal ok")
    thermal = load("thermal_signoff_flowlab.json")
    check(thermal.get("ok") is True, "thermal_signoff ok")
    tmax = (thermal.get("thermal") or {}).get("t_max_c")
    check(tmax is not None and float(tmax) < 85.0, f"HotSpot t_max_c={tmax} under 85")
    check((thermal.get("thermal") or {}).get("engine") == "hotspot", "thermal engine is hotspot")

    sta_ir = load("sta_ir_aware_flowlab.json")
    check(sta_ir.get("ok") is True, "STA IR-aware report ok")

    signoff_all = load("signoff_all_flowlab.json")
    check(signoff_all.get("ok") is False, "signoff_all stays fail while LVS fails")

    gate = load("gate_sim_flowlab.json")
    check(gate.get("ok") is True, "gate_sim report ok")
    check(gate.get("status") == "READY", "gate_sim READY")

    spice = load("spice_engines_flowlab.json")
    check(spice.get("xyce_status") == "READY", "Xyce N4 READY in spice_engines")
    check((spice.get("xyce_n4") or {}).get("ok") is True, "Xyce N4 gold ok")

    pex = load("analytical_pex_flowlab.json")
    check(pex.get("ok") is True, "analytical_pex ok")
    fc = pex.get("fastercap") or {}
    check(fc.get("status") == "READY", "FasterCap BEM READY")
    check(float(fc.get("c_couple_fF") or 0) > 0, "FasterCap Cc > 0")
    print("ALL test_signoff_honesty PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

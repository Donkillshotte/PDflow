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
    check(lvs.get("ok") is True, "LVS compare is a real KLayout match")
    check(int(lvs.get("must_connect") or 0) == 2, "LVS leftover must-connect stays 2")
    msgs = ((lvs.get("artifact_parse") or {}).get("lvsdb") or {}).get("messages") or []
    check(any("DFF_X2" in str(m) for m in msgs), "leftover messages name DFF_X2")
    tail = ((lvs.get("artifact_parse") or {}).get("log") or {}).get("tail") or []
    check(any("CONGRATULATIONS" in str(x) or "Netlists match" in str(x) for x in tail), "LVS log keeps the match line")
    check(not any("Netlists don't match" in str(x) for x in tail), "LVS log has no mismatch line")
    stamp = ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/.lvs.ok"
    check(stamp.exists(), "matched LVS stamps .lvs.ok")

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
    check(signoff_all.get("ok") is True, "signoff_all follows the four pillars")
    pillars = signoff_all.get("pillars") or {}
    check(all(pillars.get(k, {}).get("ok") for k in ("timing", "geometry", "equivalence", "power")), "four signoff pillars ok")
    leftover = signoff_all.get("leftover") or {}
    check(int(leftover.get("must_connect") or 0) == 2, "signoff_all leftover must-connect is 2")
    check("DFF_X2" in (leftover.get("circuits") or []), "signoff_all leftover names DFF_X2")
    check("leftover must-connect 2" in str(signoff_all.get("summary")), "signoff_all summary names leftover")
    eq = pillars.get("equivalence") or {}
    check(int((eq.get("leftover") or {}).get("must_connect") or 0) == 2, "equivalence pillar carries leftover")
    ledger_all = signoff_all.get("ir_mesh_ledger") or {}
    check(ledger_all.get("comparable") is False, "signoff_all IR ledger not comparable")
    check(int(ledger_all.get("n_meshes") or 0) >= 5, "signoff_all ledger has five meshes")
    check("stamp_signoff_all.py" in (ROOT / "learn/scripts/run_signoff_all.sh").read_text(), "signoff_all restamps leftover from pillar reports")
    from stamp_signoff_all import leftover_from_lvs, build
    parsed = leftover_from_lvs(lvs)
    check(parsed is not None and parsed["must_connect"] == 2, "stamp leftover_from_lvs reads LVS")
    check("DFF_X2" in parsed["circuits"], "stamp leftover_from_lvs names DFF_X2")
    rebuilt = build("flowlab")
    check(rebuilt.get("ok") is True, "stamp rebuild is ok")
    check(int((rebuilt.get("leftover") or {}).get("must_connect") or 0) == 2, "stamp rebuild leftover")
    pwr = load("power_signoff_flowlab.json")
    ledger = pwr.get("ir_mesh_ledger") or {}
    check(ledger.get("comparable") is False, "power_signoff IR meshes are not comparable")
    ids = {m.get("id") for m in (ledger.get("meshes") or [])}
    check({"gold_dynamic_ir", "chip_pdn", "vyges_em_ir"} <= ids, "ledger names gold, chip, and vyges")

    gate = load("gate_sim_flowlab.json")
    check(gate.get("ok") is True, "gate_sim report ok")
    check(gate.get("status") == "READY", "gate_sim READY")

    vl = load("vectorless_flowlab.json")
    check(vl.get("ok") is True, "vectorless report ok")
    dyn_src = str((vl.get("dynamic") or {}).get("source") or "")
    check("gcd_gate.vcd" in dyn_src, "dynamic source is gate VCD")
    check("tb_gcd_gate/dut" in dyn_src, "dynamic VCD scope is tb_gcd_gate/dut")

    gc = load("gridcheck_flowlab.json")
    check(gc.get("ok") is True, "gridcheck flowlab ok")
    check(gc.get("vdd_connected") is True and gc.get("vss_connected") is True, "gridcheck VDD+VSS")

    spice = load("spice_engines_flowlab.json")
    check(spice.get("xyce_status") == "READY", "Xyce N4 READY in spice_engines")
    check((spice.get("xyce_n4") or {}).get("ok") is True, "Xyce N4 gold ok")

    pex = load("analytical_pex_flowlab.json")
    check(pex.get("ok") is True, "analytical_pex ok")
    fc = pex.get("fastercap") or {}
    check(fc.get("status") == "READY", "FasterCap BEM READY")
    check(float(fc.get("c_couple_fF") or 0) > 0, "FasterCap Cc > 0")

    ccs = load("ccs_char_flowlab.json")
    check(ccs.get("ok") is True, "ccs_char report ok")
    check(ccs.get("status") == "READY", "ccs_char READY")
    check((ccs.get("official_probe") or {}).get("status") == "GAP", "official Nangate liberty stays NLDM GAP")
    check((ccs.get("official_probe") or {}).get("n_ccs_tables", 1) == 0, "official lib has zero CCS tables")
    check(int(ccs.get("n_ccs_tables") or 0) >= 30, "sidecar has ≥15 cells × rise/fall")
    check(int(ccs.get("n_cells") or 0) >= 15, "at least 15 GCD combo cells characterized")
    check("INV_X1" in (ccs.get("cells") or []), "INV_X1 still in sidecar")
    check("AOI21_X1" in (ccs.get("cells") or []), "AOI21_X1 in sidecar")
    check("CLKBUF_X1" in (ccs.get("cells") or []), "CLKBUF_X1 in sidecar")
    check(0.25 <= float(ccs.get("delay_ratio_vs_nldm") or 0) <= 4.0, "PTM delay within band of NLDM")
    sidecar = ROOT / "learn/sim/lib/nangate45_ptm_ccs_sidecar.lib"
    inv = ROOT / "learn/sim/lib/INV_X1_ptm45_ccs.lib"
    check(sidecar.is_file(), "multi-cell sidecar CCS liberty exists")
    check(inv.is_file(), "INV_X1 sidecar still exists")
    check("output_current_fall" in sidecar.read_text(), "sidecar contains output_current_fall")
    check("cell (NAND2_X1)" in sidecar.read_text(), "sidecar includes NAND2_X1")

    deep = load("lvs_deep_flowlab.json")
    check(deep.get("ok") is True, "deep transistor LVS matches")
    check((deep.get("transistor") or {}).get("ok") is True, "transistor compare is match")
    check(int(deep.get("n_filtered_masters") or 0) >= 30, "filtered CDL keeps used masters")
    check(int((deep.get("transistor") or {}).get("n_flatten", 99)) == 0, "unused library flatten is gone")
    check(deep.get("well_to_rails") is True, "deep LVS maps wells to VDD/VSS")
    check(deep.get("fill_from_def") is True, "deep LVS injects FILL from DEF")
    check((ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/.lvs.ok").exists(), "transistor match may stamp .lvs.ok")
    print("ALL test_signoff_honesty PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Physical-meaning checks on real-design lab artifacts.

Does not restamp gold 45.298 mV. Does not invent IR for designs without a mesh.
Quantities stay labeled: ORFS PSM static ≠ Dynamic IR TRAN ≠ educational STA IR.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"
CAMPAIGN = ROOT / "learn/sim/dse/campaign_experiments.jsonl"
LEDGER = ROOT / "learn/sim/dse/lab_physics_ledger.json"
MISSING_LAB = (
    ("sta_signoff", "sta_signoff_flowlab.json", "OpenSTA nominal signoff JSON"),
    ("vectorless", "vectorless_flowlab.json", "vectorless activity / IR artifact"),
    ("chip_pdn", "pdn_chip_ir_flowlab.json", "chip-level PDN IR"),
    ("system_pdn", "system_pdn_flowlab.json", "package + die system PDN"),
    ("thermal", "thermal_signoff_flowlab.json", "thermal / electrothermal snapshot"),
)

VDD = 1.1
ALPHA = 1.3
GOLD_MV = 45.298
CURRENT_MV = 6.075
PERIOD_GCD_NS = 0.46
SLOTS = (
    ("gcd", 0.46),
    ("spi", 1.0),
    ("ibex", 2.2),
    ("aes", 0.82),
    ("dynamic_node", 6.0),
)


def _read(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text().splitlines():
        t = line.strip()
        if not t:
            continue
        try:
            rows.append(json.loads(t))
        except json.JSONDecodeError:
            continue
    return rows


def _check(
    checks: list[dict],
    *,
    id: str,
    ok: bool,
    status: str,
    quantity: str,
    value,
    bound: str,
    note: str,
    design: str = "gcd",
) -> None:
    checks.append(
        {
            "id": id,
            "design": design,
            "ok": ok,
            "status": status,
            "quantity": quantity,
            "value": value,
            "bound": bound,
            "note": note,
        }
    )


def _frac_vdd(ir_mv: float) -> float:
    return (ir_mv * 1e-3) / VDD


def validate() -> dict:
    checks: list[dict] = []
    gold = _read(REPORTS / "dynamic_ir_flowlab.json") or {}
    direct = _read(REPORTS / "dynamic_ir_flowlab_direct.json") or {}
    amg = _read(REPORTS / "dynamic_ir_flowlab_amg.json") or {}
    ras = _read(REPORTS / "dynamic_ir_flowlab_ras.json") or {}
    krylov = _read(REPORTS / "dynamic_ir_flowlab_krylov.json") or {}
    sta_ir = _read(REPORTS / "sta_ir_aware_flowlab.json") or {}
    aes = _read(REPORTS / "dse_aes.json") or {}
    camp = _jsonl(CAMPAIGN)

    gold_mv = gold.get("worst_droop_mv")
    gold_ok = bool(gold.get("gold")) and gold_mv is not None and abs(float(gold_mv) - GOLD_MV) < 0.02
    _check(
        checks,
        id="gold_sentinel",
        ok=gold_ok,
        status="READY" if gold_ok else "GAP",
        quantity="Dynamic IR gold (reference_run)",
        value=gold_mv,
        bound=f"{GOLD_MV} mV frozen",
        note="Historical Solver A on the reference extract. Not current_run. Do not restamp.",
    )

    cur = None
    win = direct.get("windowed") or {}
    if win.get("worst_droop_mv") is not None:
        cur = float(win["worst_droop_mv"])
    elif direct.get("worst_droop_mv") is not None:
        cur = float(direct["worst_droop_mv"])
    cur_ok = cur is not None and abs(cur - CURRENT_MV) < 0.05
    _check(
        checks,
        id="current_run_droop",
        ok=cur_ok,
        status="READY" if cur_ok else "GAP",
        quantity="Dynamic IR current_run (finish mesh)",
        value=cur,
        bound=f"~{CURRENT_MV} mV on this extract",
        note="Same GCD, different extract/activity window than gold 45.298. Do not mix.",
    )

    split_ok = gold_ok and cur is not None and abs(float(gold_mv) - cur) > 20.0
    _check(
        checks,
        id="gold_vs_current_split",
        ok=split_ok,
        status="READY" if split_ok else "GAP",
        quantity="|gold − current|",
        value=None if cur is None or gold_mv is None else abs(float(gold_mv) - cur),
        bound="> 20 mV so the two runs stay distinct",
        note="If these collapsed, someone restamped gold or mixed extracts.",
    )

    if cur is not None:
        frac = _frac_vdd(cur)
        _check(
            checks,
            id="current_ir_vs_vdd",
            ok=0 < frac < 0.05,
            status="READY" if 0 < frac < 0.05 else "FAIL",
            quantity="current_run IR / Vdd",
            value=round(frac * 100, 3),
            bound="(0, 5)% of 1.1 V for a bumped GCD",
            note="6 mV on 1.1 V is ~0.55%. Typical on-die IR for this size, not a Voltus sign-off.",
        )

    if gold_mv is not None:
        gfrac = _frac_vdd(float(gold_mv))
        _check(
            checks,
            id="gold_ir_vs_vdd",
            ok=0 < gfrac < 0.15,
            status="READY" if 0 < gfrac < 0.15 else "FAIL",
            quantity="gold IR / Vdd",
            value=round(gfrac * 100, 3),
            bound="(0, 15)% — hot educational mesh, still below rail collapse",
            note="45 mV is 4.1% of Vdd. Physically a stressed PDN, not a second product number.",
        )

    def _droop(blob: dict) -> float | None:
        w = blob.get("windowed") or {}
        if w.get("worst_droop_mv") is not None:
            return float(w["worst_droop_mv"])
        if blob.get("worst_droop_mv") is not None:
            return float(blob["worst_droop_mv"])
        return None

    a_mv, b_mv, d_mv, c_mv = _droop(direct), _droop(amg), _droop(ras), _droop(krylov)
    if a_mv is not None and b_mv is not None:
        d_ab = abs(a_mv - b_mv)
        _check(
            checks,
            id="solver_a_vs_amg",
            ok=d_ab < 0.05,
            status="READY" if d_ab < 0.05 else "FAIL",
            quantity="|A DirectLU − B SA-AMG|",
            value=d_ab,
            bound="< 0.05 mV on the same mesh",
            note="Same operator, two solvers. Agreement is the physics check, not a new extract.",
        )
    if a_mv is not None and d_mv is not None:
        d_ad = abs(a_mv - d_mv)
        _check(
            checks,
            id="solver_a_vs_ras",
            ok=d_ad < 0.05,
            status="READY" if d_ad < 0.05 else "FAIL",
            quantity="|A DirectLU − D RAS|",
            value=d_ad,
            bound="< 0.05 mV",
            note="Schwarz residual vs gold LU on the finish mesh.",
        )
    if a_mv is not None and c_mv is not None:
        d_ac = abs(a_mv - c_mv)
        _check(
            checks,
            id="solver_a_vs_krylov",
            ok=d_ac < 0.05,
            status="READY" if d_ac < 0.05 else "WATCH",
            quantity="|A DirectLU − C Krylov|",
            value=d_ac,
            bound="< 0.05 mV preferred; MOR may sit a few tens of µV off",
            note="Krylov is a reduced model. A few tens of µV is residual, not a new IR story.",
        )

    sta = sta_ir.get("sta") or {}
    slack = sta.get("slack_ns")
    slack_ir = sta.get("slack_ir_ns")
    deg = sta.get("degradation_ps")
    n_join, n_gates = sta.get("n_joined"), sta.get("n_gates")
    path_ok = (
        slack is not None
        and slack_ir is not None
        and float(slack_ir) <= float(slack) + 1e-12
        and n_join == n_gates == 18
    )
    _check(
        checks,
        id="sta_ir_path",
        ok=path_ok,
        status="READY" if path_ok else "GAP",
        quantity="STA slack → slack_ir",
        value={"slack_ns": slack, "slack_ir_ns": slack_ir, "joined": f"{n_join}/{n_gates}"},
        bound="slack_ir ≤ slack; 18/18 gates on the GCD worst max path",
        note="NLDM typical-V scaled by (Vdd/V_inst)^1.3. Not Tempus, not a second liberty.",
    )

    gates = sta_ir.get("path_gates") or []
    if gates and slack is not None and slack_ir is not None:
        recon = sum(float(g.get("delay_ir_ns") or 0) - float(g.get("delay_ns") or 0) for g in gates)
        expect = float(slack) - float(slack_ir)
        match = abs(recon - expect) < 1e-9
        _check(
            checks,
            id="sta_ir_reconstruct",
            ok=match,
            status="READY" if match else "FAIL",
            quantity="Σ(delay_ir − delay) vs slack − slack_ir",
            value={"reconstructed_ns": recon, "reported_ns": expect},
            bound="equal to 1e-9 ns",
            note="The extra delay is exactly the sum of per-gate IR scales. No hidden pad.",
        )
        # Per-gate Ohmic check: scale ≈ (Vdd/V)^α
        scale_ok = True
        for g in gates:
            if not g.get("joined") or g.get("v_inst") is None:
                continue
            v = max(float(g["v_inst"]), 0.25 * VDD)
            want = (VDD / v) ** ALPHA
            got = float(g.get("scale") or 0)
            if abs(want - got) > 1e-6:
                scale_ok = False
                break
        _check(
            checks,
            id="sta_ir_alpha_law",
            ok=scale_ok and bool(gates),
            status="READY" if scale_ok and gates else "FAIL",
            quantity="per-gate scale vs (Vdd/V_inst)^α",
            value=ALPHA,
            bound="α = 1.3 on every joined gate",
            note="Delay stretch tracks local voltage, not a tap-average fiction.",
        )

    if deg is not None:
        frac_p = (float(deg) * 1e-3) / PERIOD_GCD_NS
        _check(
            checks,
            id="sta_ir_vs_period",
            ok=0 <= frac_p < 0.01,
            status="READY" if 0 <= frac_p < 0.01 else "WATCH",
            quantity="extra delay / clock period",
            value=round(frac_p * 100, 4),
            bound="< 1% of 0.46 ns on this GCD",
            note="0.62 ps is 0.13% of the period. Slack stays MET. IR-aware STA is a perturbation, not a new timing close.",
        )

    # ORFS static IR on official slots
    slot_rows: list[dict] = []
    for design, clk in SLOTS:
        same = [
            r
            for r in camp
            if r.get("design") == design
            and abs(float(r.get("clock_ns") or 0) - clk) < 1e-6
            and r.get("status") == "done"
            and r.get("finish_wns_ns") is not None
        ]
        base = next((r for r in same if r.get("role") == "base"), None)
        ir_v = None if base is None else base.get("ir_drop_v")
        ir_mv = None if ir_v is None else float(ir_v) * 1e3
        wns = None if base is None else base.get("finish_wns_ns")
        if ir_mv is None:
            _check(
                checks,
                id=f"orfs_ir_{design}",
                ok=False,
                status="GAP",
                quantity="ORFS PSM static IR (base)",
                value=None,
                bound="finish report present",
                note="No campaign finish IR for this slot.",
                design=design,
            )
            slot_rows.append({"design": design, "clock_ns": clk, "status": "GAP"})
            continue
        frac = _frac_vdd(ir_mv)
        plausible = 0 < ir_mv < 0.25 * VDD * 1e3
        watch = ir_mv > 50.0
        _check(
            checks,
            id=f"orfs_ir_{design}",
            ok=plausible,
            status="WATCH" if watch and plausible else ("READY" if plausible else "FAIL"),
            quantity="ORFS analyze_power_grid IR (base finish)",
            value={"ir_mv": ir_mv, "wns_ns": wns, "pct_vdd": round(frac * 100, 3)},
            bound="(0, 250) mV; WATCH if > 50 mV",
            note=(
                "ORFS static IR is not Dynamic IR TRAN and not STA IR. "
                + (
                    "Large core / more current — physically a hotter grid, still not Voltus."
                    if watch
                    else "Same order as a small Nangate die with the tutorial PDN."
                )
            ),
            design=design,
        )
        slot_rows.append(
            {
                "design": design,
                "clock_ns": clk,
                "status": "WATCH" if watch else "READY",
                "orfs_ir_mv": ir_mv,
                "finish_wns_ns": wns,
                "n_cooks": len(same),
            }
        )

    gcd_orfs = next((s for s in slot_rows if s.get("design") == "gcd" and s.get("orfs_ir_mv") is not None), None)
    if gcd_orfs and cur is not None:
        ratio = float(gcd_orfs["orfs_ir_mv"]) / cur
        _check(
            checks,
            id="gcd_orfs_vs_dynamic",
            ok=0.3 <= ratio <= 3.0,
            status="READY" if 0.3 <= ratio <= 3.0 else "WATCH",
            quantity="ORFS static / Dynamic IR current_run",
            value=round(ratio, 3),
            bound="within 3× (same die, different engines)",
            note="6.67 mV PSM vs 6.08 mV TRAN is the same physical story at different fidelity.",
        )

    aes_static = aes.get("f4_static_ir_mv")
    aes_dyn = (aes.get("cloud_agent_f4") or {}).get("dynamic_ir_mv")
    if aes_static is not None:
        _check(
            checks,
            id="aes_f4_static",
            ok=0 < float(aes_static) < 50,
            status="READY",
            quantity="AES F4 static IR (febe6804241c mesh)",
            value=aes_static,
            bound="(0, 50) mV; not gold 45.298",
            note="Different extract from campaign ORFS 81 mV. Do not average them.",
            design="aes",
        )
    if aes_static is not None and aes_dyn is not None:
        _check(
            checks,
            id="aes_transient_gt_static",
            ok=float(aes_dyn) >= float(aes_static) * 0.8,
            status="READY" if float(aes_dyn) >= float(aes_static) * 0.8 else "WATCH",
            quantity="AES cloud TRAN vs its own static",
            value={"static_mv": aes_static, "dynamic_mv": aes_dyn},
            bound="TRAN ≥ ~0.8× static on a comparable mesh",
            note="di/dt + package L raise droop above DC. Cloud 17.7 mV is not the 73k-R 6.95 mV extract.",
            design="aes",
        )
        _check(
            checks,
            id="aes_not_gold",
            ok=(aes.get("cloud_agent_f4") or {}).get("gold") is not True,
            status="READY",
            quantity="AES F4 gold flag",
            value=False,
            bound="must stay gold=false",
            note="AES must never restamp GCD 45.298.",
            design="aes",
        )

    dse = _read(REPORTS / "dse_flowlab.json") or {}
    win_ir = dse.get("winning_ir_pdn_mv")
    win_st = dse.get("winning_static_mv")
    if win_ir is not None:
        _check(
            checks,
            id="dse_winning_ir_not_gold",
            ok=abs(float(win_ir) - GOLD_MV) > 1.0,
            status="READY" if abs(float(win_ir) - GOLD_MV) > 1.0 else "FAIL",
            quantity="DSE winning_ir_pdn vs gold sentinel",
            value=win_ir,
            bound="must not equal 45.298 mV",
            note="Candidate F4 catalog mesh (decap / pkg L). A different extract from gold and from current_run TRAN.",
        )
    if win_st is not None:
        _check(
            checks,
            id="dse_winning_static",
            ok=0 < float(win_st) < 50,
            status="READY" if 0 < float(win_st) < 50 else "WATCH",
            quantity="DSE winning_static_mv",
            value=win_st,
            bound="(0, 50) mV on a candidate mesh",
            note="Educational F4 static. Not ORFS analyze_power_grid 6.67 mV.",
        )
    amg, ras, kry = dse.get("ir_champ_amg_mv"), dse.get("ir_champ_ras_mv"), dse.get("ir_champ_krylov_mv")
    if amg is not None and ras is not None:
        d_ar = abs(float(amg) - float(ras))
        _check(
            checks,
            id="dse_amg_vs_ras",
            ok=d_ar < 0.05,
            status="READY" if d_ar < 0.05 else "FAIL",
            quantity="|DSE AMG-c − RAS-c|",
            value=d_ar,
            bound="< 0.05 mV on the champion extract",
            note="Same operator, two solvers inside the controller. Agreement is the check.",
        )
    if amg is not None and kry is not None:
        d_ak = abs(float(amg) - float(kry))
        _check(
            checks,
            id="dse_amg_vs_krylov",
            ok=d_ak < 0.05,
            status="READY" if d_ak < 0.05 else "WATCH",
            quantity="|DSE AMG-c − Krylov-c|",
            value=d_ak,
            bound="< 0.05 mV preferred",
            note="Krylov MOR on the champion extract. Tens of µV is residual, not a new IR story.",
        )

    for key, fname, label in MISSING_LAB:
        blob = _read(REPORTS / fname)
        _check(
            checks,
            id=f"artifact_{key}",
            ok=blob is not None,
            status="READY" if blob is not None else "GAP",
            quantity=label,
            value=None if blob is None else fname,
            bound="report present on disk",
            note=(
                "Present — still not foundry sign-off."
                if blob is not None
                else "Not materialized in this checkout. Do not invent a number."
            ),
        )

    ready = sum(1 for c in checks if c["status"] == "READY" and c["ok"])
    fail = [c["id"] for c in checks if c["status"] == "FAIL" or (c["status"] != "GAP" and not c["ok"] and c["status"] != "WATCH")]
    watch = [c["id"] for c in checks if c["status"] == "WATCH"]
    gap = [c["id"] for c in checks if c["status"] == "GAP"]
    return {
        "ok": not fail,
        "kind": "lab_physics",
        "vdd": VDD,
        "alpha": ALPHA,
        "gold_ir_mv": GOLD_MV,
        "current_ir_mv": CURRENT_MV,
        "n_ready": ready,
        "n_checks": len(checks),
        "fail": fail,
        "watch": watch,
        "gap": gap,
        "slots": slot_rows,
        "checks": checks,
        "not": [
            "PrimeTime / Tempus IR-aware STA",
            "Voltus / RedHawk sign-off",
            "gold 45.298 mV restamp",
            "averaging ORFS static with Dynamic IR TRAN",
        ],
        "note": (
            "Physical meaning here is internal consistency + rail-scale sanity on real "
            "Nangate finishes. It is not foundry correlation."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=REPORTS / "lab_physics_flowlab.json")
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    args = ap.parse_args()
    report = validate()
    text = json.dumps(report, indent=2) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    args.ledger.write_text(text)
    print(
        f"LAB_PHYSICS_DONE ok={report['ok']} "
        f"ready={report['n_ready']}/{report['n_checks']} "
        f"watch={len(report['watch'])} gap={len(report['gap'])} fail={report['fail']}"
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

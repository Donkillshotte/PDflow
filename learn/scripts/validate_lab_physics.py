#!/usr/bin/env python3
"""Validate physical consistency of the live lab artifacts.

The validator never loads an external metric or compares a new design to an
unrelated run. It checks current-run finiteness, units,
same-extract solver residuals, and joins between the current STA and IR map.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"
LEDGER = ROOT / "learn/sim/dse/lab_physics_ledger.json"
VDD = 1.1
ALPHA = 1.3


def _read(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _number(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _check(checks: list[dict], *, ident: str, ok: bool, quantity: str,
           value, bound: str, note: str, design: str = "gcd",
           status: str | None = None) -> None:
    checks.append({
        "id": ident,
        "design": design,
        "ok": bool(ok),
        "status": status or ("READY" if ok else "FAIL"),
        "quantity": quantity,
        "value": value,
        "bound": bound,
        "note": note,
    })


def _droop(blob: dict) -> float | None:
    window = blob.get("windowed") or {}
    value = _number(window.get("worst_droop_mv") if window else None)
    if value is not None:
        return value
    value = _number(blob.get("worst_droop_mv"))
    if value is not None:
        return value
    value = _number((blob.get("dynamic") or {}).get("worst_droop"))
    return value * 1e3 if value is not None else None


def _evidence_usable(blob: dict) -> bool:
    """Return whether a report contains usable measurement evidence.

    ``ok`` is intentionally not used as the only signal here.  The live chip
    IR, Dynamic IR and vyges reports are honest ``PROXY`` results: their
    measurements and provenance are valid (``evidence_status=PASS``), but the
    evidence is not sufficient to close Product signoff.  Lab physics must
    validate the measurement itself without turning that boundary into a
    false FAIL.
    """

    evidence_status = str(blob.get("evidence_status") or "").upper()
    if evidence_status:
        return evidence_status == "PASS"
    return bool(blob.get("ok"))


def _ir_fraction(mv: float) -> float:
    return mv * 1e-3 / VDD


def _same_run_solver_checks(checks: list[dict], direct: dict) -> None:
    a = _droop(direct)
    solvers = {
        "direct": a,
        "amg": _number((direct.get("solver_b") or {}).get("worst_droop_mv")),
        "krylov": _number((direct.get("solver_c") or {}).get("worst_droop_mv")),
        "ras": _number((direct.get("solver_d") or {}).get("worst_droop_mv")),
    }
    _check(checks, ident="live_dynamic_ir", ok=_evidence_usable(direct) and a is not None and a > 0,
           quantity="current Dynamic IR droop", value=a,
           bound="finite and positive on the current extract",
           note="The value comes from this invocation's Dynamic IR report.")
    for name, value in solvers.items():
        if name == "direct" or value is None or a is None:
            continue
        delta = abs(value - a)
        _check(checks, ident=f"solver_direct_vs_{name}", ok=delta < 0.05,
               quantity=f"|DirectLU − {name}| on the same extract", value=delta,
               bound="< 0.05 mV", note="Same-run numerical residual; no external target is used.",
               status="READY" if delta < 0.05 else "FAIL")


def validate() -> dict:
    checks: list[dict] = []
    direct = _read(REPORTS / "dynamic_ir_flowlab_direct.json") or {}
    sta_ir = _read(REPORTS / "sta_ir_aware_flowlab.json") or {}
    dse = _read(REPORTS / "dse_flowlab.json") or {}
    _same_run_solver_checks(checks, direct)

    droop = _droop(direct)
    if droop is not None:
        frac = _ir_fraction(droop)
        _check(checks, ident="dynamic_ir_vs_vdd", ok=0 < frac < 0.25,
               quantity="current Dynamic IR / Vdd", value=round(frac * 100, 4),
               bound="between 0 and 25% of the active rail",
               note="Rail-scale sanity check for the current extract.")

    sta = sta_ir.get("sta") or {}
    slack = _number(sta.get("slack_ns"))
    slack_ir = _number(sta.get("slack_ir_ns"))
    n_joined, n_gates = sta.get("n_joined"), sta.get("n_gates")
    path_ok = (slack is not None and slack_ir is not None and slack_ir <= slack + 1e-12
               and n_joined is not None and n_gates is not None
               and int(n_joined) == int(n_gates) and int(n_gates) > 0)
    _check(checks, ident="sta_ir_path", ok=path_ok,
           quantity="current STA slack → IR-aware slack",
           value={"slack_ns": slack, "slack_ir_ns": slack_ir, "joined": f"{n_joined}/{n_gates}"},
           bound="all current path gates joined; IR slack does not improve slack",
           note="The STA path and voltage map are consumed from the same live finish.")

    gates = sta_ir.get("path_gates") or []
    if gates and slack is not None and slack_ir is not None:
        recon = sum((_number(g.get("delay_ir_ns")) or 0) - (_number(g.get("delay_ns")) or 0) for g in gates)
        expect = slack - slack_ir
        _check(checks, ident="sta_ir_reconstruct", ok=abs(recon - expect) < 1e-9,
               quantity="sum of live per-gate IR delay increments", value={"reconstructed_ns": recon, "reported_ns": expect},
               bound="equal within 1e-9 ns", note="Current report is internally reconstructible.")
        scales_ok = True
        for gate in gates:
            v = _number(gate.get("v_inst"))
            scale = _number(gate.get("scale"))
            if gate.get("joined") and v is not None and scale is not None:
                scales_ok &= abs(scale - (VDD / max(v, 0.25 * VDD)) ** ALPHA) < 1e-6
        _check(checks, ident="sta_ir_alpha_law", ok=scales_ok,
               quantity="live per-gate voltage scaling", value=ALPHA,
               bound="scale=(Vdd/V_inst)^alpha", note="The current IR-aware path exposes its calculation.")

    chip = _read(REPORTS / "pdn_chip_ir_flowlab.json")
    system = _read(REPORTS / "system_pdn_flowlab.json")
    vyges = _read(REPORTS / "vyges_em_ir_flowlab.json")
    for ident, blob, path, field, scale in (
        ("chip_pdn", chip, "pdn_chip_ir_flowlab.json", ("transient", "worst_droop"), 1e3),
        ("system_pdn", system, "system_pdn_flowlab.json", ("transient", "droop_mv"), 1.0),
        ("vyges_em_ir", vyges, "vyges_em_ir_flowlab.json", ("vyges", "worst_ir"), 1.0),
    ):
        if blob is None:
            _check(checks, ident=f"artifact_{ident}", ok=False, status="GAP",
                   quantity=ident, value=None, bound="current report present",
                   note="No value is invented when the current artifact is absent.")
            continue
        if blob.get("status") == "GAP":
            _check(checks, ident=f"artifact_{ident}", ok=False, status="GAP",
                   quantity=f"current {ident}", value=blob.get("summary"),
                   bound="current engine result or explicit GAP",
                   note=f"The current run reported an unavailable optional engine for {path}.")
            continue
        value = blob
        for key in field:
            value = value.get(key) if isinstance(value, dict) else None
        if ident == "vyges_em_ir" and isinstance(value, dict):
            value = value.get("drop")
        value = _number(value)
        value = value * scale if value is not None else None
        _check(checks, ident=f"artifact_{ident}", ok=_evidence_usable(blob) and value is not None and value > 0,
               quantity=f"current {ident}", value=value,
               bound="finite and positive current-run measurement",
               note=f"Read from {path}; this mesh remains separate from the others.")

    if dse:
        dse_values = [
            _number(dse.get("winning_ir_pdn_mv")),
            _number(dse.get("ir_champ_amg_mv")),
            _number(dse.get("ir_champ_ras_mv")),
            _number(dse.get("ir_champ_krylov_mv")),
        ]
        has_dse_measurement = any(v is not None and v > 0 for v in dse_values)
        if has_dse_measurement:
            _check(
                checks,
                ident="dse_live_measurements",
                ok=bool(dse.get("ok")) and has_dse_measurement,
                quantity="current DSE IR measurements",
                value=dse_values,
                bound="finite positive measurements from the current DSE run",
                note="DSE values are reported from this invocation only.",
                status="READY" if bool(dse.get("ok")) else "FAIL",
            )
        else:
            _check(
                checks,
                ident="dse_live_measurements",
                ok=False,
                status="GAP",
                quantity="current DSE IR measurements",
                value=dse_values,
                bound="current DSE run emits an F4 measurement",
                note="The current DSE controller report contains no F4 champion measurement; no value is invented.",
            )
        live_solver = [v for v in dse_values[1:] if v is not None]
        if has_dse_measurement and dse_values[1] is not None and live_solver:
            residuals = [abs(v - dse_values[1]) for v in live_solver]
            _check(checks, ident="dse_solver_consistency", ok=max(residuals, default=0) < 0.05,
                   quantity="DSE same-run solver residuals", value=residuals,
                   bound="< 0.05 mV", note="Only solvers for the current extract are compared.")

    missing = {
        "sta_signoff": "sta_signoff_flowlab.json",
        "vectorless": "vectorless_flowlab.json",
        "thermal": "thermal_signoff_flowlab.json",
    }
    for ident, filename in missing.items():
        blob = _read(REPORTS / filename)
        _check(checks, ident=f"artifact_{ident}", ok=blob is not None,
               status="READY" if blob is not None else "GAP", quantity=ident,
               value=filename if blob is not None else None,
               bound="current report present", note="Missing artifacts stay GAP.")

    fail = [c["id"] for c in checks if c["status"] == "FAIL" or (not c["ok"] and c["status"] not in {"GAP", "WATCH"})]
    ready = sum(1 for c in checks if c["status"] == "READY" and c["ok"])
    return {
        "ok": not fail,
        "kind": "lab_physics",
        "vdd": VDD,
        "alpha": ALPHA,
        "comparison_scope": "live artifacts; same-live-extract solver comparisons only",
        "n_ready": ready,
        "n_checks": len(checks),
        "fail": fail,
        "watch": [c["id"] for c in checks if c["status"] == "WATCH"],
        "gap": [c["id"] for c in checks if c["status"] == "GAP"],
        "checks": checks,
        "not": ["foundry sign-off", "cross-extract numeric matching", "external result replay"],
        "note": "Physical checks use only current reports and explicit same-run numerical residuals.",
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
    print(f"LAB_PHYSICS_DONE ok={report['ok']} ready={report['n_ready']}/{report['n_checks']} gap={len(report['gap'])} fail={report['fail']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

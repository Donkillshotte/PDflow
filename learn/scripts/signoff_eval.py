#!/usr/bin/env python3
"""Evaluate signoff metrics against learn/signoff/golden-gcd.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_golden(repo: Path) -> dict:
    p = repo / "learn/signoff/golden-gcd.json"
    return json.loads(p.read_text())


def within_max(actual: float, target: float, tol_pct: float) -> bool:
    """Metric must stay at or above target (e.g. WNS/TNS — higher is better)."""
    slack = abs(target) * tol_pct
    return actual >= target - slack


def within_min(actual: float, target: float, tol_pct: float) -> bool:
    """Metric must stay at or below target (e.g. violations — lower is better)."""
    slack = abs(target) * tol_pct if target else tol_pct
    return actual <= target + slack


def evaluate_timing(metrics: dict, golden: dict) -> dict:
    g = golden["timing"]
    tol = golden["tolerance"]["timing_pct"]
    checks = []
    for key, label, mode in [
        ("wns_ns", "WNS max (ns)", "max"),
        ("tns", "TNS max", "max"),
        ("setup_violations", "Setup violations", "min"),
        ("period_min_ns", "period_min (ns)", "max"),
    ]:
        if key not in metrics or metrics[key] is None:
            continue
        actual = float(metrics[key])
        target_key = {
            "wns_ns": "wns_max_ns",
            "tns": "tns_max",
            "setup_violations": "setup_violations_max",
            "period_min_ns": "period_min_ns",
        }[key]
        target = float(g[target_key])
        ok = within_max(actual, target, tol) if mode == "max" else within_min(actual, target, tol)
        checks.append(
            {
                "id": key,
                "label": label,
                "actual": actual,
                "target": target,
                "ok": ok,
            }
        )
    return {"checks": checks, "ok": all(c["ok"] for c in checks) if checks else None}


def evaluate_geometry(metrics: dict, golden: dict) -> dict:
    g = golden["geometry"]
    checks = []
    for key, label in [
        ("route_drc_lines", "Route DRC report lines"),
        ("gds_drc_violations", "KLayout GDS DRC violations"),
    ]:
        if key not in metrics:
            continue
        actual = int(metrics[key])
        target = int(g["route_drc_lines_max" if key == "route_drc_lines" else "gds_drc_violations_max"])
        ok = actual <= target
        checks.append({"id": key, "label": label, "actual": actual, "target": target, "ok": ok})
    return {"checks": checks, "ok": all(c["ok"] for c in checks) if checks else None}


def evaluate_equivalence(metrics: dict, golden: dict) -> dict:
    g = golden["equivalence"]
    checks = []
    if "lvs_pass" in metrics:
        ok = bool(metrics["lvs_pass"])
        checks.append(
            {
                "id": "lvs_pass",
                "label": "LVS clean",
                "actual": ok,
                "target": True,
                "ok": ok,
                "note": g.get("educational_note"),
            }
        )
    return {"checks": checks, "ok": all(c["ok"] for c in checks) if checks else None}


def evaluate_power(metrics: dict, golden: dict) -> dict:
    g = golden["power"]
    tol = golden["tolerance"]["power_pct"]
    mapping = [
        ("chip_static_ir_mv", "chip_static_ir_mv_max", "Chip static IR (mV)"),
        ("chip_transient_droop_mv", "chip_transient_droop_mv_max", "Chip transient droop (mV)"),
        ("system_droop_mv", "system_droop_mv_max", "System droop (mV)"),
        ("system_zmax_mohm", "system_zmax_mohm_max", "System Zmax (mΩ)"),
    ]
    checks = []
    for key, gkey, label in mapping:
        if key not in metrics:
            continue
        actual = float(metrics[key])
        target = float(g[gkey])
        ok = within_min(actual, target, tol)
        checks.append({"id": key, "label": label, "actual": actual, "target": target, "ok": ok})
    return {"checks": checks, "ok": all(c["ok"] for c in checks) if checks else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--pillar", choices=["timing", "geometry", "equivalence", "power", "all"])
    ap.add_argument("--metrics", type=Path, required=True, help="JSON file with metrics")
    ap.add_argument("--out", type=Path, help="Write evaluation JSON")
    args = ap.parse_args()

    golden = load_golden(args.repo)
    metrics = json.loads(args.metrics.read_text())
    evaluators = {
        "timing": evaluate_timing,
        "geometry": evaluate_geometry,
        "equivalence": evaluate_equivalence,
        "power": evaluate_power,
    }
    pillars = list(evaluators.keys()) if args.pillar == "all" else [args.pillar]
    result = {"pillar": args.pillar, "pillars": {}}
    all_ok = True
    for p in pillars:
        ev = evaluators[p](metrics.get(p, metrics), golden)
        result["pillars"][p] = ev
        if ev.get("ok") is False:
            all_ok = False
    result["ok"] = all_ok
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

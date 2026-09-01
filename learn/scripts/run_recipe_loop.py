#!/usr/bin/env python3
"""Product loop: pick recipes from circuit state, cook only if selected.

No design name in the picker. Skips a recipe already tried (same id or knobs).

Usage:
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py --dry-run
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py --max-cooks 4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_LEARN = Path(__file__).resolve().parents[1]
_ROOT = _LEARN.parent
if str(_LEARN) not in sys.path:
    sys.path.insert(0, str(_LEARN))

from dse.experiments import DESIGN_CATALOG, ExperimentLog  # noqa: E402
from dse.knob_catalog import config_mk_for, parse_config_defaults  # noqa: E402
from dse.recipe_select import (  # noqa: E402
    already_tried,
    floorplan_locked,
    select_recipes,
    state_from_exp,
)

DESIGNS = ("gcd", "spi", "ibex", "aes", "dynamic_node")


def _base(log: ExperimentLog, design: str, clock_ns: float):
    clk = f"{float(clock_ns):.3f}"
    for e in log.all():
        if e.design != design or e.role != "base" or e.finish_wns_ns is None:
            continue
        if f"{float(e.clock_ns):.3f}" == clk:
            return e
    return None


def _same_slot(log: ExperimentLog, design: str, clock_ns: float):
    clk = f"{float(clock_ns):.3f}"
    out = []
    for e in log.all():
        if e.design != design:
            continue
        if f"{float(e.clock_ns):.3f}" == clk:
            out.append(e)
    return out


def plan_for(design: str, log: ExperimentLog) -> dict:
    clock = float(DESIGN_CATALOG[design]["clk_ns"])
    base = _base(log, design, clock)
    if base is None:
        return {"design": design, "clock_ns": clock, "skip": "no_base", "pick": []}
    cfg = config_mk_for(design)
    defaults = parse_config_defaults(cfg)
    locked = floorplan_locked(cfg)
    rows = _same_slot(log, design, clock)
    from dse.knob_catalog import RECIPES

    already = {r["id"] for r in RECIPES if already_tried(rows, r["id"], defaults)}
    pick = select_recipes(state_from_exp(base), locked_floorplan=locked, already=already)
    return {
        "design": design,
        "clock_ns": clock,
        "base": base.variant,
        "wns_ns": base.finish_wns_ns,
        "density": base.util,
        "ir_worst_v": base.ir_drop_v,
        "locked_floorplan": locked,
        "already": sorted(already),
        "pick": pick,
        "skip": None if pick else "nothing_to_try",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--designs", nargs="+", default=list(DESIGNS))
    p.add_argument("--phase", default="L1")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-cooks", type=int, default=4)
    args = p.parse_args(argv)

    log = ExperimentLog()
    plans = [plan_for(d, log) for d in args.designs]
    print(json.dumps({"plans": plans, "dry_run": args.dry_run}, indent=2, default=str))

    if args.dry_run:
        return 0

    cooked = 0
    cook = _LEARN / "scripts" / "cook_recipe.py"
    for pl in plans:
        for rid in pl.get("pick") or []:
            if cooked >= args.max_cooks:
                print(json.dumps({"stop": "max_cooks", "cooked": cooked}))
                return 0
            print(json.dumps({"cook": True, "design": pl["design"], "recipe": rid, "phase": args.phase}))
            rc = subprocess.run(
                [
                    sys.executable,
                    str(cook),
                    "--design",
                    pl["design"],
                    "--recipes",
                    rid,
                    "--phase",
                    args.phase,
                ],
                cwd=str(_ROOT),
                check=False,
            ).returncode
            cooked += 1
            print(json.dumps({"cooked": rid, "design": pl["design"], "rc": rc}))
            if rc != 0:
                print(json.dumps({"warn": "cook_failed", "design": pl["design"], "recipe": rid}))
    print(json.dumps({"ok": True, "cooked": cooked}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

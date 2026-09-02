#!/usr/bin/env python3
"""Product DSE coordinator: review finishes, pick the next physical cooks.

RTL stays fixed. Default is --auto: cover holes, then improve slots with
no win, then TPE tune. --deepen keeps the old two-axis grid.

Usage:
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py --dry-run
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py --max-cooks 2
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py --cover-all --dry-run
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py --improve --dry-run
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py --deepen --dry-run
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
from dse.knob_catalog import RECIPES, config_mk_for, parse_config_defaults  # noqa: E402
from dse.recipe_select import (  # noqa: E402
    CHEAP_FIRST,
    already_tried,
    combo_already_tried,
    inferred_recipe_ids,
    propose_deepen,
    propose_improve,
    recipes_still_open,
    select_recipes,
    state_from_exp,
)
from dse.win_rule import verdict  # noqa: E402

DESIGNS = CHEAP_FIRST


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


def _product_wins(rows, base) -> int:
    if base is None:
        return 0
    n = 0
    for e in rows:
        if e is base or e.role == "base":
            continue
        if e.status != "done" or e.finish_wns_ns is None:
            continue
        if verdict(e, base) == "win":
            n += 1
    return n


def plan_for(design: str, log: ExperimentLog) -> dict:
    clock = float(DESIGN_CATALOG[design]["clk_ns"])
    base = _base(log, design, clock)
    if base is None:
        return {"design": design, "clock_ns": clock, "skip": "no_base", "pick": []}
    cfg = config_mk_for(design)
    defaults = parse_config_defaults(cfg)
    locked = True
    rows = _same_slot(log, design, clock)
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


def cover_plan_for(design: str, log: ExperimentLog) -> dict:
    clock = float(DESIGN_CATALOG[design]["clk_ns"])
    base = _base(log, design, clock)
    cfg = config_mk_for(design)
    defaults = parse_config_defaults(cfg)
    locked = True
    rows = _same_slot(log, design, clock)
    from dse.tune_transfer import infer_walls

    pick = (
        recipes_still_open(
            rows,
            defaults,
            locked_floorplan=locked,
            walls=infer_walls(log.all()),
        )
        if base
        else []
    )
    return {
        "design": design,
        "clock_ns": clock,
        "mode": "cover",
        "base": None if base is None else base.variant,
        "wns_ns": None if base is None else base.finish_wns_ns,
        "locked_floorplan": locked,
        "pick": pick,
        "skip": "no_base" if base is None else (None if pick else "covered"),
    }


def cover_queue(log: ExperimentLog, designs: list[str]) -> list[dict]:
    """(design, recipe) still unmeasured, cheapest design first."""
    jobs = []
    for d in designs:
        pl = cover_plan_for(d, log)
        for rid in pl.get("pick") or []:
            jobs.append({"design": d, "recipes": [rid], "id": rid, "mode": "cover"})
    return jobs


def improve_queue(log: ExperimentLog, designs: list[str]) -> list[dict]:
    """Combos of win axes on slots that still have no product win."""
    jobs = []
    for d in designs:
        clock = float(DESIGN_CATALOG[d]["clk_ns"])
        base = _base(log, d, clock)
        if base is None:
            continue
        locked = True
        rows = _same_slot(log, d, clock)
        wins = _product_wins(rows, base)
        already = []
        for e in rows:
            extra = e.extra or {}
            rids = extra.get("recipe_ids") or []
            if len(rids) >= 2:
                already.append(list(rids))
        already_ids = {
            r
            for extra in ((e.extra or {}) for e in rows)
            for r in (extra.get("recipe_ids") or ([extra["recipe_id"]] if extra.get("recipe_id") else []))
        }
        for parts in propose_improve(
            locked_floorplan=locked,
            already_parts=already,
            product_wins=wins,
            wns_ns=base.finish_wns_ns,
            already=already_ids,
        ):
            if combo_already_tried(rows, parts):
                continue
            jobs.append(
                {
                    "design": d,
                    "recipes": parts,
                    "id": "_".join(parts),
                    "mode": "improve",
                }
            )
    return jobs


def deepen_queue(log: ExperimentLog, designs: list[str]) -> list[dict]:
    """Pair winning physical axes that have not been cooked together."""
    jobs = []
    for d in designs:
        clock = float(DESIGN_CATALOG[d]["clk_ns"])
        base = _base(log, d, clock)
        if base is None:
            continue
        cfg = config_mk_for(d)
        defaults = parse_config_defaults(cfg)
        locked = True
        rows = _same_slot(log, d, clock)
        win_ids: list[str] = []
        already: list[list[str]] = []
        for e in rows:
            if e.role == "base":
                continue
            parts = inferred_recipe_ids(e, defaults)
            if len(parts) >= 2:
                already.append(list(parts))
            if e.status != "done" or e.finish_wns_ns is None:
                continue
            if verdict(e, base) != "win":
                continue
            for rid in parts:
                if rid not in win_ids:
                    win_ids.append(rid)
        for parts in propose_deepen(win_ids, locked_floorplan=locked, already_parts=already):
            if combo_already_tried(rows, parts):
                continue
            jobs.append(
                {
                    "design": d,
                    "recipes": parts,
                    "id": "_".join(parts),
                    "mode": "deepen",
                }
            )
    return jobs


def coordinate(log: ExperimentLog, designs: list[str], deepen: bool = False) -> dict:
    """Review the registry and choose the next direction. One policy.

    Default after cover+improve is TPE tune. `--deepen` keeps the old
    two-axis grid as an override.
    """
    review = []
    for d in designs:
        clock = float(DESIGN_CATALOG[d]["clk_ns"])
        base = _base(log, d, clock)
        cfg = config_mk_for(d)
        defaults = parse_config_defaults(cfg)
        locked = True
        rows = _same_slot(log, d, clock) if base else []
        from dse.tune_transfer import infer_walls

        holes = (
            recipes_still_open(
                rows,
                defaults,
                locked_floorplan=locked,
                walls=infer_walls(log.all()),
            )
            if base
            else []
        )
        wins = _product_wins(rows, base)
        review.append(
            {
                "design": d,
                "base": None if base is None else base.variant,
                "wns_ns": None if base is None else base.finish_wns_ns,
                "holes": holes,
                "product_wins": wins,
                "locked_floorplan": locked,
            }
        )
    cover = cover_queue(log, designs)
    if cover:
        return {
            "decision": "cover",
            "why": "Missing catalog measurements. Fill holes first, cheapest finish.",
            "review": review,
            "jobs": cover,
        }
    improve = improve_queue(log, designs)
    if improve:
        return {
            "decision": "improve",
            "why": "Catalog covered. Slots with no wins: try new knobs/combos.",
            "review": review,
            "jobs": improve,
        }
    if deepen:
        deep = deepen_queue(log, designs)
        if deep:
            return {
                "decision": "deepen",
                "why": "Override --deepen: combine axes that already won (grid, not TPE).",
                "review": review,
                "jobs": deep,
            }
        return {
            "decision": "stop",
            "why": "Nothing to cook: catalog covered, improve exhausted, winning combos already tried or absent.",
            "review": review,
            "jobs": [],
        }
    from dse.tune_warm import preview_tune

    for d in designs:
        prev = preview_tune(d, log)
        if not prev.get("admissible"):
            continue
        return {
            "decision": "tune",
            "why": "Catalog covered and improve exhausted. TPE on the same die, one finish at a time.",
            "design": d,
            "warm": prev.get("warm"),
            "queue": prev.get("queue"),
            "next_fp": prev.get("next_fp"),
            "next_title": prev.get("next_title"),
            "review": review,
            "jobs": [],
        }
    return {
        "decision": "stop",
        "why": "Nothing to cook: catalog covered, improve exhausted, no slot admissible for tune.",
        "review": review,
        "jobs": [],
    }


def _cook_one(design: str, recipes: list[str], phase: str) -> int:
    cook = _LEARN / "scripts" / "cook_recipe.py"
    cmd = [
        sys.executable,
        str(cook),
        "--design",
        design,
        "--recipes",
        *recipes,
        "--phase",
        phase,
    ]
    print(json.dumps({"cook": True, "design": design, "recipes": recipes, "phase": phase}))
    rc = subprocess.run(cmd, cwd=str(_ROOT), check=False).returncode
    print(json.dumps({"cooked": recipes, "design": design, "rc": rc}))
    if rc != 0:
        print(json.dumps({"warn": "cook_failed", "design": design, "recipes": recipes}))
    return rc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--designs", nargs="+", default=list(DESIGNS))
    p.add_argument("--phase", default="L1")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-cooks", type=int, default=4)
    p.add_argument(
        "--cover-all",
        action="store_true",
        help="Cook every unmeasured catalog recipe, cheapest design first.",
    )
    p.add_argument(
        "--improve",
        action="store_true",
        help="On slots with no product win, cook combos of independent axes.",
    )
    p.add_argument(
        "--deepen",
        action="store_true",
        help="Override: pair winning catalog axes instead of TPE tune.",
    )
    p.add_argument(
        "--select-only",
        action="store_true",
        help="Old selector only: cook if circuit state asks, ignore cover/improve/tune.",
    )
    args = p.parse_args(argv)

    log = ExperimentLog()
    if args.cover_all:
        jobs = cover_queue(log, args.designs)
        plans = [cover_plan_for(d, log) for d in args.designs]
        print(json.dumps({"mode": "cover", "plans": plans, "jobs": jobs, "dry_run": args.dry_run}, indent=2, default=str))
    elif args.improve:
        jobs = improve_queue(log, args.designs)
        print(json.dumps({"mode": "improve", "jobs": jobs, "dry_run": args.dry_run}, indent=2, default=str))
    elif args.select_only:
        plans = [plan_for(d, log) for d in args.designs]
        print(json.dumps({"mode": "select", "plans": plans, "dry_run": args.dry_run}, indent=2, default=str))
        jobs = []
        for pl in plans:
            for rid in pl.get("pick") or []:
                jobs.append({"design": pl["design"], "recipes": [rid], "id": rid, "mode": "select"})
    else:
        coord = coordinate(log, args.designs, deepen=args.deepen)
        print(json.dumps({**coord, "dry_run": args.dry_run}, indent=2, default=str))
        if coord.get("decision") == "tune":
            if args.dry_run:
                return 0
            tpe = _LEARN / "scripts" / "run_tpe.py"
            cmd = [
                sys.executable,
                str(tpe),
                "--design",
                str(coord["design"]),
                "--max-cooks",
                str(args.max_cooks),
            ]
            print(json.dumps({"tune": True, "design": coord["design"], "max_cooks": args.max_cooks}))
            return subprocess.run(cmd, cwd=str(_ROOT), check=False).returncode
        jobs = list(coord.get("jobs") or [])

    if args.dry_run:
        return 0

    cooked = 0
    for job in jobs:
        if cooked >= args.max_cooks:
            print(json.dumps({"stop": "max_cooks", "cooked": cooked}))
            return 0
        _cook_one(job["design"], list(job["recipes"]), args.phase)
        cooked += 1
    print(json.dumps({"ok": True, "cooked": cooked}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

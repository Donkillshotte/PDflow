"""Warm-start and enqueue helpers for TPE. No Optuna import."""
from __future__ import annotations

from typing import Any

from .floorplan import FLOORPLAN_RECIPES, moves_floorplan, official_box
from .knob_catalog import resolve_many
from .recipe_select import VERY_CLOSED_NS, combo_already_tried, inferred_recipe_ids, propose_deepen, propose_improve
from .tune_space import fingerprint, knobs_from_extra, params_from_recipes, project_knobs
from .tune_transfer import infer_walls, params_blocked, transfer_enqueue
from .win_rule import verdict


def same_clock(exp: Any, clock_ns: float) -> bool:
    return f"{float(exp.clock_ns):.3f}" == f"{float(clock_ns):.3f}"


def is_fresh_synth(exp: Any) -> bool:
    extra = getattr(exp, "extra", None) or {}
    return bool(extra.get("fresh_synth"))


def warm_params(exp: Any, defaults: dict[str, float], base: Any) -> dict[str, Any] | None:
    """Project a finished same-die row onto the TPE space, or None."""
    if getattr(exp, "status", None) != "done" or getattr(exp, "finish_wns_ns", None) is None:
        return None
    if getattr(exp, "role", None) == "base":
        return None
    if is_fresh_synth(exp):
        return None
    extra = getattr(exp, "extra", None) or {}
    rids = extra.get("recipe_ids") or ([extra["recipe_id"]] if extra.get("recipe_id") else [])
    if any(r in FLOORPLAN_RECIPES for r in rids):
        return None
    if moves_floorplan(exp, base) or verdict(exp, base) == "wrong_die":
        return None
    knobs = knobs_from_extra(extra)
    if extra.get("core_utilization") is not None and "CORE_UTILIZATION" in defaults:
        knobs.setdefault("CORE_UTILIZATION", str(extra["core_utilization"]))
    return project_knobs(knobs, defaults)


def collect_warm(
    rows: list[Any],
    defaults: dict[str, float],
    base: Any,
) -> list[tuple[dict[str, Any], Any]]:
    seen: set[str] = set()
    out: list[tuple[dict[str, Any], Any]] = []
    for e in rows:
        params = warm_params(e, defaults, base)
        if params is None:
            continue
        fp = fingerprint(params, defaults)
        if fp in seen:
            continue
        seen.add(fp)
        out.append((params, e))
    return out


def enqueue_params(
    rows: list[Any],
    defaults: dict[str, float],
    win_ids: list[str],
    already_parts: list[list[str]],
    *,
    all_rows: list[Any] | None = None,
    design: str | None = None,
    walls: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Deepen combos of this slot, then up to 3 cross-design win mechanisms."""
    walls = walls if walls is not None else infer_walls(all_rows or rows)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for parts in propose_deepen(win_ids, locked_floorplan=True, already_parts=already_parts):
        if combo_already_tried(rows, parts):
            continue
        params = params_from_recipes(parts, defaults)
        if params is None or params_blocked(params, walls) is not None:
            continue
        fp = fingerprint(params, defaults)
        if fp in seen:
            continue
        seen.add(fp)
        out.append(params)
    if all_rows and design:
        out.extend(
            transfer_enqueue(
                all_rows,
                design,
                defaults,
                already_fps=seen,
                walls=walls,
            )
        )
    return out


def tune_admissible(base: Any, rows: list[Any], defaults: dict[str, float], design: str) -> bool:
    """True if this slot should run TPE. No design-name branch."""
    if base is None or official_box(design) is None:
        return False
    if getattr(base, "finish_wns_ns", None) is None:
        return False
    wins = 0
    for e in rows:
        if e is base or getattr(e, "role", None) == "base":
            continue
        if getattr(e, "status", None) != "done" or getattr(e, "finish_wns_ns", None) is None:
            continue
        if verdict(e, base) == "win":
            wins += 1
    very_closed = float(base.finish_wns_ns) >= VERY_CLOSED_NS
    already = set()
    for e in rows:
        extra = getattr(e, "extra", None) or {}
        for r in extra.get("recipe_ids") or ([extra["recipe_id"]] if extra.get("recipe_id") else []):
            already.add(r)
    improve = propose_improve(
        locked_floorplan=True,
        product_wins=wins,
        wns_ns=base.finish_wns_ns,
        already=already,
    )
    if very_closed and wins == 0 and not improve:
        return False
    return True


def win_ids_from_rows(rows: list[Any], base: Any, defaults: dict[str, float]) -> list[str]:
    ids: list[str] = []
    for e in rows:
        if getattr(e, "role", None) == "base":
            continue
        if getattr(e, "status", None) != "done" or getattr(e, "finish_wns_ns", None) is None:
            continue
        if verdict(e, base) != "win":
            continue
        for rid in inferred_recipe_ids(e, defaults):
            if rid not in ids:
                ids.append(rid)
    return ids


def already_combo_parts(rows: list[Any], defaults: dict[str, float]) -> list[list[str]]:
    out: list[list[str]] = []
    for e in rows:
        if getattr(e, "role", None) == "base":
            continue
        parts = inferred_recipe_ids(e, defaults)
        if len(parts) >= 2:
            out.append(list(parts))
    return out


def base_of(log: Any, design: str):
    from .experiments import DESIGN_CATALOG

    clock = float(DESIGN_CATALOG[design]["clk_ns"])
    clk = f"{clock:.3f}"
    for e in log.all():
        if e.design != design or e.role != "base" or e.finish_wns_ns is None:
            continue
        if f"{float(e.clock_ns):.3f}" == clk:
            return e
    return None


def slot_rows(log: Any, design: str) -> list[Any]:
    from .experiments import DESIGN_CATALOG

    clock = float(DESIGN_CATALOG[design]["clk_ns"])
    clk = f"{clock:.3f}"
    return [
        e
        for e in log.all()
        if e.design == design and f"{float(e.clock_ns):.3f}" == clk
    ]


def preview_tune(design: str, log: Any | None = None) -> dict[str, Any]:
    """Dry-run payload for the coordinator. No Optuna."""
    from .experiments import ExperimentLog
    from .knob_catalog import config_mk_for, parse_config_defaults

    log = log or ExperimentLog()
    defaults = parse_config_defaults(config_mk_for(design))
    base = base_of(log, design)
    rows = slot_rows(log, design)
    ok = tune_admissible(base, rows, defaults, design)
    if not ok:
        return {
            "ok": False,
            "admissible": False,
            "design": design,
            "warm": 0,
            "queue": 0,
            "next_fp": None,
            "next_title": None,
        }
    warm = collect_warm(rows, defaults, base)
    win_ids = win_ids_from_rows(rows, base, defaults)
    already = already_combo_parts(rows, defaults)
    walls = infer_walls(log.all())
    queue = enqueue_params(
        rows,
        defaults,
        win_ids,
        already,
        all_rows=log.all(),
        design=design,
        walls=walls,
    )
    nxt = queue[0] if queue else None
    from .tune_space import fingerprint, title_of_params

    return {
        "ok": True,
        "admissible": True,
        "design": design,
        "warm": len(warm),
        "queue": len(queue),
        "next_fp": fingerprint(nxt, defaults) if nxt else None,
        "next_title": title_of_params(nxt) if nxt else None,
        "win_ids": win_ids,
        "walls": [f"{w.kind}:{w.value}" for w in walls],
    }

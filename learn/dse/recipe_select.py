"""Pick catalog recipes from circuit state. No design name in the rules."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .knob_catalog import RECIPES, by_id, resolve

# Already the default, or never a product win in campaign.
_NEVER = frozenset({"synth_area", "synth_delay"})
# Default synth method: already the official netlist. Do not recook.
# hold_margin / place_notiming are improve-only until they take a win.
SKIP_COVER = frozenset({"synth_area", "hold_margin", "place_notiming", "cts_sparser", "repair_skip"})
# Cheapest live finish first. Cover-all uses this order, not the selector.
CHEAP_FIRST = ("gcd", "spi", "ibex", "aes", "dynamic_node")

# Closed by a wide margin: cooking will not take a product win.
VERY_CLOSED_NS = 0.100
SPARSE = 0.15
HIGH_IR_V = 0.020
DENSE = 0.55
MANY_BUFFERS = 30
MAX_PICK = 2

# Combos of independent win axes. Used after a slot has no product win.
# Floorplan parts are dropped when the die is locked — no design name.
IMPROVE_COMBOS: tuple[tuple[str, ...], ...] = (
    ("place_denser", "repair_setup_margin"),
    ("aspect_wide", "place_denser"),
    ("core_tighter", "place_denser"),
    ("place_denser", "repair_half_tns"),
)
# On a die already closed by a wide margin, repair combos are no-ops.
# Try unused physical knobs that can still move area / power / IR.
CLOSED_IMPROVE: tuple[str, ...] = (
    "place_notiming",
    "hold_margin",
    "cts_sparser",
    "repair_skip",
)


def floorplan_locked(config_mk: Path | str | None) -> bool:
    """True when the config pins the die (FLOORPLAN_DEF / DIE_AREA)."""
    if not config_mk:
        return False
    p = Path(config_mk)
    if not p.is_file():
        return False
    text = p.read_text()
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        if "FLOORPLAN_DEF" in s or (s.startswith("export DIE_AREA") and "=" in s):
            return True
    return False


def state_from_exp(exp: Any) -> dict[str, Any]:
    return {
        "wns_ns": exp.finish_wns_ns,
        "tns_ns": exp.finish_tns_ns,
        "setup_viol": exp.setup_violation_count,
        "density": exp.util,
        "repair_buffer": exp.repair_buffer,
        "ir_worst_v": exp.ir_drop_v,
        "power_w": exp.power_w,
        "cells": exp.stdcell_count,
        "area_um2": exp.stdcell_um2,
    }


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def select_recipes(
    state: dict[str, Any],
    *,
    locked_floorplan: bool = False,
    already: set[str] | None = None,
    max_pick: int = MAX_PICK,
) -> list[str]:
    """Return catalog ids that can fire on this state. Order = priority."""
    already = already or set()
    wns = _f(state.get("wns_ns"))
    tns = _f(state.get("tns_ns"))
    dens = _f(state.get("density"))
    ir = _f(state.get("ir_worst_v"))
    buf = state.get("repair_buffer")
    viol = state.get("setup_viol")
    cells = state.get("cells")

    closed = wns is not None and wns >= 0.0 and (tns is None or tns >= -1e-12) and not viol
    very_closed = closed and wns is not None and wns >= VERY_CLOSED_NS
    late = wns is not None and wns < 0.0
    sparse = dens is not None and dens < SPARSE
    dense = dens is not None and dens >= DENSE
    high_ir = ir is not None and ir >= HIGH_IR_V
    many_buf = buf is not None and int(buf) >= MANY_BUFFERS

    if very_closed:
        return []

    ranked: list[str] = []

    def add(rid: str) -> None:
        if rid in _NEVER or rid in already or rid in ranked:
            return
        ranked.append(rid)

    if (late or (high_ir and dens is not None and SPARSE <= dens <= 0.75)) and not locked_floorplan:
        add("core_tighter")
    if (late or many_buf) and not sparse:
        add("place_denser")
    if late and not closed:
        add("repair_setup_margin")
    if late and dense:
        add("place_sparser")
        add("cell_pad_plus")
    if late and not locked_floorplan:
        add("aspect_wide")
    if late and cells is not None and int(cells) >= 2000:
        add("synth_hier")

    return ranked[: max(0, int(max_pick))]


def is_synth_delay_run(exp: Any) -> bool:
    """ABC-speed finishes already measure synth_delay. Do not recook them."""
    role = str(getattr(exp, "role", "") or "")
    if role in ("abc_speed", "dse_fast"):
        return True
    variant = str(getattr(exp, "variant", "") or "")
    if "abcspeed" in variant or variant.endswith("_synth_delay"):
        return True
    extra = getattr(exp, "extra", None) or {}
    knobs = extra.get("knobs") or {}
    return str(knobs.get("ABC_SPEED", "0")) in ("1", "true", "True")


def already_tried(exps: list[Any], recipe_id: str, defaults: dict[str, float]) -> bool:
    """True if this recipe (or the same knobs) already finished on these rows."""
    try:
        want = resolve(recipe_id, defaults)
    except KeyError:
        want = {}
    for e in exps:
        if getattr(e, "status", None) not in ("done", "stopped_by_policy"):
            continue
        if recipe_id == "synth_delay" and is_synth_delay_run(e):
            return True
        extra = getattr(e, "extra", None) or {}
        rids = extra.get("recipe_ids") or ([extra["recipe_id"]] if extra.get("recipe_id") else [])
        if recipe_id in rids:
            return True
        if rids and set(rids) == {recipe_id}:
            return True
        variant = str(getattr(e, "variant", "") or "")
        if variant.endswith("_" + recipe_id):
            return True
        knobs = extra.get("knobs") or {}
        lb = knobs.get("PLACE_DENSITY_LB_ADDON", extra.get("place_density_lb_addon"))
        util = knobs.get("CORE_UTILIZATION", extra.get("core_utilization"))
        if recipe_id == "place_denser" and lb is not None:
            if abs(float(lb) - float(want.get("PLACE_DENSITY_LB_ADDON", 0.25))) < 0.011:
                return True
        if recipe_id == "core_tighter" and util is not None and "CORE_UTILIZATION" in want:
            if abs(float(util) - float(want["CORE_UTILIZATION"])) < 1.0:
                return True
        if recipe_id == "place_sparser" and lb is not None and "PLACE_DENSITY_LB_ADDON" in want:
            if abs(float(lb) - float(want["PLACE_DENSITY_LB_ADDON"])) < 0.011:
                return True
        if recipe_id == "core_looser" and util is not None and "CORE_UTILIZATION" in want:
            if abs(float(util) - float(want["CORE_UTILIZATION"])) < 1.0:
                return True
    return False


def recipes_still_open(
    rows: list[Any],
    defaults: dict[str, float],
    *,
    locked_floorplan: bool = False,
) -> list[str]:
    """Catalog ids not yet measured on these rows. Skips default synth and locked floorplan."""
    out: list[str] = []
    for rec in RECIPES:
        rid = rec["id"]
        if rid in SKIP_COVER:
            continue
        if locked_floorplan and rec.get("stage") == "floorplan":
            continue
        if already_tried(rows, rid, defaults):
            continue
        out.append(rid)
    return out


def combo_already_tried(exps: list[Any], parts: list[str]) -> bool:
    want = set(parts)
    for e in exps:
        if getattr(e, "status", None) not in ("done", "stopped_by_policy"):
            continue
        extra = getattr(e, "extra", None) or {}
        rids = extra.get("recipe_ids") or []
        if rids and set(rids) == want:
            return True
        variant = str(getattr(e, "variant", "") or "")
        if variant.endswith("_" + "_".join(parts)):
            return True
    return False


def propose_improve(
    *,
    locked_floorplan: bool = False,
    already_parts: list[list[str]] | None = None,
    product_wins: int = 0,
    wns_ns: float | None = None,
    already: set[str] | None = None,
) -> list[list[str]]:
    """If this slot has no product win, try the next physical experiment.

    No design name. Floorplan parts drop when the die is locked.
    A very-closed die skips repair combos (measured no-ops) and tries
    unused knobs that can still move area / power / IR.
    """
    if int(product_wins) > 0:
        return []
    already = already or set()
    seen = {tuple(p) for p in (already_parts or [])}
    out: list[list[str]] = []
    closed = wns_ns is not None and float(wns_ns) >= VERY_CLOSED_NS
    if closed:
        for rid in CLOSED_IMPROVE:
            if rid in already or (rid,) in seen:
                continue
            out.append([rid])
        return out
    for combo in IMPROVE_COMBOS:
        parts = [p for p in combo if not (locked_floorplan and by_id(p).get("stage") == "floorplan")]
        if len(parts) < 2:
            continue
        key = tuple(parts)
        if key in seen:
            continue
        seen.add(key)
        out.append(list(parts))
    return out


def catalog_ids() -> list[str]:
    return [r["id"] for r in RECIPES]


# Touch by_id so a typo in _NEVER / CLOSED_IMPROVE fails import-time.
for _rid in _NEVER:
    by_id(_rid)
for _rid in CLOSED_IMPROVE:
    by_id(_rid)

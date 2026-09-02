"""Product floorplan is pinned: same die area, size, and shape as the official run.

CORE_UTILIZATION / CORE_ASPECT_RATIO are not product knobs. Historical
floorplan cooks stay in the log as lab measurements; they do not win.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .geometry import parse_def_geometry

FLOORPLAN_RECIPES = frozenset({"core_tighter", "core_looser", "aspect_wide"})
# Area/core may snap a hair; shape is caught via recipes/knobs.
_AREA_FRAC = 0.02


def official_def(design: str) -> Path | None:
    from .experiments import DESIGN_CATALOG, REPO

    orfs = (DESIGN_CATALOG.get(design) or {}).get("orfs_design") or design
    flow = REPO / "tools/OpenROAD-flow-scripts/flow/results/nangate45"
    for variant in (f"camp_{design}_base", "flowlab"):
        p = flow / orfs / variant / "6_final.def"
        if p.is_file():
            return p
    return None


def official_box(design: str) -> dict[str, str] | None:
    """DIE_AREA / CORE_AREA strings for make. None if the DEF is missing."""
    p = official_def(design)
    if p is None:
        return None
    g = parse_def_geometry(p)
    die = g.get("die_area")
    core = g.get("core_area")
    if not die or not core:
        return None
    return {"DIE_AREA": str(die), "CORE_AREA": str(core)}


def is_floorplan_recipe(recipe_id: str) -> bool:
    return recipe_id in FLOORPLAN_RECIPES


def _recipe_ids(obj: Any) -> list[str]:
    extra = getattr(obj, "extra", None) or {}
    rids = extra.get("recipe_ids") or ([extra["recipe_id"]] if extra.get("recipe_id") else [])
    return [str(r) for r in rids]


def _knobs(obj: Any) -> dict[str, Any]:
    extra = getattr(obj, "extra", None) or {}
    return dict(extra.get("knobs") or {})


def _fnum(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _util(obj: Any) -> float | None:
    extra = getattr(obj, "extra", None) or {}
    v = extra.get("core_utilization")
    if v is None:
        v = _knobs(obj).get("CORE_UTILIZATION")
    return _fnum(v)


def _aspect(obj: Any) -> float | None:
    return _fnum(_knobs(obj).get("CORE_ASPECT_RATIO"))


def moves_floorplan(cand: Any, base: Any | None = None) -> bool:
    """True if this row changed die area, size, or shape vs the slot base."""
    rids = _recipe_ids(cand)
    if any(r in FLOORPLAN_RECIPES for r in rids):
        return True
    variant = str(getattr(cand, "variant", "") or "")
    if any(tag in variant for tag in FLOORPLAN_RECIPES):
        return True
    ar = _aspect(cand)
    if ar is not None and abs(ar - 1.0) > 0.05:
        return True
    if base is None:
        return False
    cu, bu = _util(cand), _util(base)
    if cu is not None and bu is not None and abs(cu - bu) >= 1.0:
        return True
    for field in ("die_um2", "core_um2"):
        new = _fnum(getattr(cand, field, None))
        old = _fnum(getattr(base, field, None))
        if new is None or old is None:
            continue
        if abs(old) < 1e-9:
            continue
        if abs(new - old) / abs(old) > _AREA_FRAC:
            return True
    return False

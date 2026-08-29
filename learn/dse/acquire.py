"""Budget-aware fidelity / transform picker.

inspect → choose (level, fidelity) → caller evaluates. Does not flatten
architecture, ABC, util, and PDN into one acquisition over a mixed vector.
"""

from __future__ import annotations

from .memory import DesignMemory


def should_pay_f2_gpl(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_gpl: int,
    gpl_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    if n_gpl >= gpl_max:
        return False, "GPL shot already spent this run"
    if budget_left < min_s:
        return False, "wall budget would not cover OpenROAD GPL"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok"
        and c.fidelity == "F1"
        and c.qor.area_um2 is not None
        and (c.artifacts or {}).get("mapped_v")
    ]
    if not winners:
        return False, "no F1 mapped netlist to place"
    have = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("physical")
        if (c.knobs or {}).get("source") == "f2_openroad_gpl" and c.status == "ok"
    }
    if all(w.id in have for w in winners):
        return False, "every F1 winner already has a GPL child"
    return True, "promote F1 winner to OpenROAD GPL (skip_io, not finish/F5)"


def should_pay_f2_fast(mem: DesignMemory, *, n_f2: int, f2_max: int = 4) -> tuple[bool, str]:
    if n_f2 >= f2_max:
        return False, "F2-fast budget exhausted"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None
    ]
    if not winners:
        return False, "no F1 to score"
    return True, "barycenter HPWL/RUDY on the candidate netlist"


def next_fidelity(*, level: str, pred: dict | None, budget_left: float, cost_hint: dict) -> str:
    """Cheap skip stays F0; otherwise the level's measuring oracle."""
    pred = pred or {}
    if level == "logic" and pred.get("skip"):
        return "F0"
    if level in ("physical", "f2_fast"):
        return "F2"
    if level == "f2_gpl":
        return "F2"
    if level == "pdn":
        return "F4"
    need = float(cost_hint.get("F1", 2.0))
    if budget_left < need:
        return "F0"
    return "F1"

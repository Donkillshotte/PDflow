"""Human-readable labels derived from the current invocation.

This module contains no campaign table and no baked measurement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RecipeLabel:
    title: str
    does: str
    payoff: str


def _knob_label(
    lb: float | None,
    util: float | None,
    *,
    lb0: float = 0.20,
    util0: float | None = None,
) -> RecipeLabel | None:
    parts_title: list[str] = []
    parts_does: list[str] = []
    if lb is not None and abs(lb - lb0) > 1e-9:
        direction = "denser placement" if lb > lb0 else "sparser placement"
        parts_title.append(direction)
        parts_does.append(f"PLACE_DENSITY_LB_ADDON={lb:g} (run baseline {lb0:g})")
    if util is not None:
        if util0 is not None and abs(util - util0) > 1e-9:
            direction = "tighter core" if util > util0 else "looser core"
            parts_title.append(direction)
            parts_does.append(f"CORE_UTILIZATION={util:g} (run baseline {util0:g})")
        else:
            parts_title.append(f"util {util:g}")
            parts_does.append(f"CORE_UTILIZATION={util:g}")
    if not parts_title:
        return None
    title = ", ".join(parts_title)
    return RecipeLabel(
        title[:1].upper() + title[1:],
        "; ".join(parts_does),
        "Observed only from this invocation.",
    )


def label_for(exp: Any) -> RecipeLabel:
    """Return a label without consulting a persistent experiment catalogue."""
    variant = getattr(exp, "variant", None) or (exp if isinstance(exp, str) else "")
    role = getattr(exp, "role", "") or ""
    clock = getattr(exp, "clock_ns", None)
    extra = getattr(exp, "extra", None) or {}
    clock_text = f" @ {clock:g} ns" if clock is not None else ""

    role_titles = {
        "base": "Current design recipe",
        "ainj": "Current source re-injection",
        "abc_speed": "ABC delay synthesis",
        "dse_small": "Current netlist exploration",
        "dse_fast": "Current synthesis exploration",
        "dse_other": "Current netlist exploration",
    }
    if role in role_titles:
        return RecipeLabel(
            role_titles[role] + clock_text,
            "Knobs and artifacts are taken from this invocation.",
            "No result is inferred without a current report.",
        )

    recipe_ids = extra.get("recipe_ids") or (
        [extra["recipe_id"]] if extra.get("recipe_id") else []
    )
    if recipe_ids:
        try:
            from dse.knob_catalog import by_id, titles_of

            records = [by_id(r) for r in recipe_ids]
            return RecipeLabel(
                titles_of(list(recipe_ids)),
                " ".join(str(r.get("does") or "") for r in records),
                "Observed only from this invocation.",
            )
        except Exception:
            pass

    derived = _knob_label(
        float(extra["place_density_lb_addon"])
        if extra.get("place_density_lb_addon") is not None
        else None,
        float(extra["core_utilization"])
        if extra.get("core_utilization") is not None
        else None,
        util0=float(extra["util_default"])
        if extra.get("util_default") is not None
        else None,
    )
    if derived:
        return derived
    notes = (getattr(exp, "notes", None) or "").strip()
    if notes:
        return RecipeLabel(notes.split(".")[0][:80], notes, "Observed only from this invocation.")
    return RecipeLabel(
        variant or "current",
        "Current invocation.",
        "No result is inferred without a current report.",
    )


def synth_method_from_exploration() -> dict[str, Any]:
    """Describe optional synthesis axes without asserting a measured winner."""
    return {
        "abc": "area",
        "ABC_AREA": 1,
        "ABC_SPEED": 0,
        "apply_to": "explicit challenger variants in this invocation",
        "never_apply_to": ["role=base"],
        "avoid_as_default": [],
        "why": "Record and compare the resulting reports from the same invocation.",
        "next_synth_axes": ["SYNTH_HIERARCHICAL", "TNS_END_PERCENT after map"],
    }

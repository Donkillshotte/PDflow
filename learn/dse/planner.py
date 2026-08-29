"""Attribution → next level. Does not flatten knobs across levels.

Physical feedback chooses *where* to search (chip→block→region→cone):
  combo IR on a module  → architecture extracts on that cone
  spatial IR region     → physical density, not more ABC
  high GRT congestion   → physical F0 / GPL, not more ABC
  otherwise             → logic BOiLS/DRiLLS, then F2-fast / budgeted GPL
"""

from __future__ import annotations

from .arch_space import plan_dpath_extracts
from .memory import DesignMemory


def plan_search(attr: dict, mem: DesignMemory, *, f2_cong: float | None) -> dict:
    modules = list(attr.get("modules") or [])
    region = attr.get("region")
    focus = modules[0] if modules else (region or "chip")
    combo = float(attr.get("combo_frac") or 0.0)
    seq = float(attr.get("seq_frac") or 0.0)
    scope = attr.get("scope") or ("logic_cone" if modules else "chip")
    steps: list[dict] = []
    _eg, _r, extracts, _st = plan_dpath_extracts()
    unseen_arch = [
        e
        for e in _prefer_extracts(extracts, combo=combo)
        if not any(c.knobs.get("extract") == e and c.status == "ok" for c in mem.by_level("architecture"))
    ]
    if scope == "logic_cone" and focus != "chip" and combo >= 0.5 and unseen_arch:
        steps.append(
            {
                "level": "architecture",
                "reason": f"combo IR {combo:.2f} on {focus} — cone extracts, no chip restart",
                "extracts": unseen_arch,
                "scope": "logic_cone",
            }
        )
    if (f2_cong is not None and f2_cong > 0.25) or (scope == "region" and region):
        why = (
            f"F2 congestion {f2_cong:.3f} — prefer physical knobs over more ABC"
            if f2_cong is not None and f2_cong > 0.25
            else f"IR region {region} — physical density, not a chip restart"
        )
        steps.append({"level": "physical", "reason": why, "scope": "region" if region else "block"})
    else:
        steps.append(
            {
                "level": "logic",
                "reason": "BOiLS SSK-GP + DRiLLS UCB on ABC sequences",
                "scope": "block" if focus != "chip" else "chip",
            }
        )
    steps.append(
        {
            "level": "f2_fast",
            "reason": "anchored barycenter HPWL/RUDY on the best F1 netlist (not make finish)",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f2_gpl",
            "reason": "budgeted OpenROAD GPL -skip_io on the F1 winner — not route/F5/IR",
            "scope": "chip",
        }
    )
    return {
        "focus": focus,
        "combo_frac": combo,
        "seq_frac": seq,
        "f2_cong": f2_cong,
        "region": region,
        "scope": scope,
        "restart_chip": False,
        "hierarchy": ["chip", "block", "region", "logic_cone"],
        "steps": steps,
    }


def _prefer_extracts(extracts: list[str], *, combo: float) -> list[str]:
    """Combo-heavy IR → compare/sub first (datapath), then zero-test."""
    prefer = ["lt_borrow", "sub_twos_complement", "eqz_or_reduce"] if combo >= 0.5 else list(extracts)
    out = [e for e in prefer if e in extracts]
    for e in extracts:
        if e not in out:
            out.append(e)
    return out

"""Attribution → next level. Does not flatten knobs across levels.

Physical feedback chooses *where* to search:
  combo IR on a module  → architecture extracts on that cone
  high GRT congestion   → physical F0, not more ABC
  otherwise             → logic BOiLS/DRiLLS, then F2-fast on the winner
"""

from __future__ import annotations

from .arch_space import plan_dpath_extracts
from .memory import DesignMemory


def plan_search(attr: dict, mem: DesignMemory, *, f2_cong: float | None) -> dict:
    modules = list(attr.get("modules") or [])
    focus = modules[0] if modules else "chip"
    combo = float(attr.get("combo_frac") or 0.0)
    seq = float(attr.get("seq_frac") or 0.0)
    steps: list[dict] = []
    _eg, _r, extracts, _st = plan_dpath_extracts()
    unseen_arch = [
        e
        for e in _prefer_extracts(extracts, combo=combo)
        if not any(c.knobs.get("extract") == e and c.status == "ok" for c in mem.by_level("architecture"))
    ]
    if focus != "chip" and combo >= 0.5 and unseen_arch:
        steps.append(
            {
                "level": "architecture",
                "reason": f"combo IR {combo:.2f} on {focus} — cone extracts, no chip restart",
                "extracts": unseen_arch,
            }
        )
    if f2_cong is not None and f2_cong > 0.25:
        steps.append(
            {
                "level": "physical",
                "reason": f"F2 congestion {f2_cong:.3f} — prefer physical knobs over more ABC",
            }
        )
    else:
        steps.append({"level": "logic", "reason": "BOiLS SSK-GP + DRiLLS UCB on ABC sequences"})
    steps.append(
        {
            "level": "f2_fast",
            "reason": "barycenter HPWL/RUDY on the best F1 netlist (not make finish)",
        }
    )
    return {
        "focus": focus,
        "combo_frac": combo,
        "seq_frac": seq,
        "f2_cong": f2_cong,
        "restart_chip": False,
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

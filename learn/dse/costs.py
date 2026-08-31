"""Empirical Fidelity cost. COST_HINT is the fallback, not the source of truth.

``estimated_cost_s`` is the p75 of ok ``cost_s`` for that fidelity on that
design. Fewer than 3 samples → ``COST_HINT``.
"""

from __future__ import annotations

import math

from .memory import DesignMemory


def p75(xs: list[float]) -> float:
    """Linear-interpolated 75th percentile. ``xs`` must be non-empty."""
    ys = sorted(float(x) for x in xs)
    n = len(ys)
    if n == 1:
        return ys[0]
    rank = 0.75 * (n - 1)
    lo = int(math.floor(rank))
    hi = min(int(math.ceil(rank)), n - 1)
    if lo == hi:
        return ys[lo]
    w = rank - lo
    return ys[lo] * (1.0 - w) + ys[hi] * w


def estimated_cost_s(
    mem: DesignMemory,
    fidelity: str,
    design_id: str,
    *,
    cost_key: str | None = None,
) -> float:
    """p75 of ok cost_s; COST_HINT when samples < 3."""
    from .fidelity import COST_HINT

    key = cost_key or fidelity
    samples = [
        float(c.cost_s)
        for c in mem.all()
        if c.status == "ok"
        and c.design_id == design_id
        and c.fidelity == fidelity
        and c.cost_s is not None
    ]
    if len(samples) < 3:
        return float(COST_HINT.get(key) or COST_HINT.get(fidelity) or 1.0)
    return p75(samples)

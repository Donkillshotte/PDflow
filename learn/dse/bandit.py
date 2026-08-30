"""Contextual bandit over refine stages. Does not flatten knobs into one arm.

Context is (depth, leftover_n, last_dyn_mv). Arms are the generic refine
stages already gated by `actions.py`. Reward is −Δ dynamic IR vs the
depth's PDN host (improvement is positive reward).
"""

from __future__ import annotations

from .frame import leftover_cells, next_stage, refine_chain
from .memory import DesignMemory


def context(mem: DesignMemory) -> dict:
    chain = refine_chain(mem)
    nxt = next_stage(mem)
    tail = chain[-1] if chain else None
    leftover = leftover_cells(mem, tail.depth) if tail else []
    dyn = None
    if tail and tail.pdn is not None and tail.pdn.qor.dynamic_ir_mv is not None:
        dyn = float(tail.pdn.qor.dynamic_ir_mv)
    elif tail and tail.extract is not None and tail.extract.qor.dynamic_ir_mv is not None:
        dyn = float(tail.extract.qor.dynamic_ir_mv)
    return {
        "depth": None if nxt is None else int(nxt["depth"]),
        "stage": None if nxt is None else str(nxt["stage"]),
        "n_frames": len(chain),
        "leftover_n": len(leftover),
        "dyn_mv": dyn,
        "via": "refine_context — not a flattened cell+PDN vector",
    }


def choose(mem: DesignMemory) -> dict | None:
    """Policy: follow next_stage. The bandit records context; it does not invent a stage."""
    nxt = next_stage(mem)
    if nxt is None:
        return None
    ctx = context(mem)
    return {**nxt, "context": ctx, "policy": "next_stage_ucb_placeholder"}


def reward_catalog_vs_pdn(mem: DesignMemory, depth: int) -> float | None:
    chain = refine_chain(mem)
    frame = next((f for f in chain if f.depth == depth), None)
    if frame is None or frame.pdn is None or not frame.catalog:
        return None
    host = frame.pdn.qor.dynamic_ir_mv
    best = min(
        (c.qor.dynamic_ir_mv for c in frame.catalog if c.qor.dynamic_ir_mv is not None),
        default=None,
    )
    if host is None or best is None:
        return None
    return float(host) - float(best)

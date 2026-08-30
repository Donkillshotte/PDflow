"""Inspect a paid F4 candidate and choose the next design-local transform.

Does not flatten architecture + ABC + util + PDN. aes never inherits GCD
``dpath``/``ctrl`` names. Missing waveforms stay missing.
"""

from __future__ import annotations

from .actions import should_pay_refine_sizeup, steer_refine_sizeup
from .attribute import inspect_f4
from .designs import resolve
from .frame import next_stage
from .memory import DesignMemory


def latest_f4(mem: DesignMemory, *, design_id: str):
    """Newest ok F4 with a static or dynamic IR number for this design."""
    spec = resolve(design_id)
    for c in reversed(list(mem.by_level("pdn"))):
        if c.design_id != spec.id or c.status != "ok":
            continue
        if c.qor.static_ir_mv is None and c.qor.dynamic_ir_mv is None:
            continue
        return c
    return None


def inspect_and_choose(mem: DesignMemory, *, design_id: str, persist: bool = True) -> dict:
    """Attribute the latest F4, persist the join, return next_stage + steer."""
    spec = resolve(design_id)
    cand = latest_f4(mem, design_id=spec.id)
    if cand is None:
        return {
            "status": "GAP",
            "reason": "no paid F4 for this design",
            "design_id": spec.id,
            "not": ["gcd leftover", "gold 45.298 restamp"],
        }
    attr = inspect_f4(cand, design_id=spec.id)
    if persist:
        mem.touch(cand)
    nxt = next_stage(mem)
    steer = None
    pay = False
    why = ""
    if nxt and nxt.get("stage") == "sizeup":
        depth = int(nxt.get("depth") or 0)
        steer = steer_refine_sizeup(mem, depth)
        pay, why = should_pay_refine_sizeup(
            mem, depth=depth, budget_left=60.0, steer=steer
        )
    return {
        "status": attr.get("status") or "READY",
        "design_id": spec.id,
        "candidate_id": cand.id,
        "attr": attr,
        "next_stage": nxt,
        "steer": steer,
        "should_pay": pay,
        "why": why,
        "not": attr.get("not"),
    }

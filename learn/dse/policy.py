"""DRiLLS-shaped sequential policy: UCB over the next ABC op.

State = (last op, attributed focus). Reward = −Δarea when a child sequence
is the parent plus one STD op. Physical knobs never enter the state.

This is a contextual bandit, not a deep RL policy. It only proposes; F1
still measures.
"""

from __future__ import annotations

import math
from collections import defaultdict

from .abc_space import BOILS_STD_OPS
from .memory import DesignMemory


def _last_op(ops: list[str]) -> str:
    return ops[-1] if ops else "∅"


def transitions(mem: DesignMemory) -> list[tuple[str, str, str, float]]:
    """(last_op, focus, next_op, reward) from logic F1 pairs."""
    by_ops: dict[tuple[str, ...], float] = {}
    focus_of: dict[tuple[str, ...], str] = {}
    for c in mem.by_level("logic"):
        if c.status != "ok" or c.qor.area_um2 is None:
            continue
        key = tuple(c.knobs.get("abc_ops") or [])
        by_ops[key] = float(c.qor.area_um2)
        mods = (c.attr or {}).get("modules") or []
        focus_of[key] = mods[0] if mods else "chip"
    out = []
    for seq, area in by_ops.items():
        if not seq:
            continue
        parent = seq[:-1]
        if parent not in by_ops:
            continue
        reward = -(area - by_ops[parent])  # improvement is positive
        out.append((_last_op(list(parent)), focus_of.get(parent, "chip"), seq[-1], reward))
    return out


def ucb_next_op(mem: DesignMemory, *, last: str, focus: str, c: float = 1.2) -> str | None:
    """UCB1 over STD ops. None if we have no statistics yet."""
    rows = transitions(mem)
    if not rows:
        return None
    stats: dict[str, list[float]] = defaultdict(list)
    for lo, fo, op, r in rows:
        if lo == last and fo == focus:
            stats[op].append(r)
    # backoff: ignore focus, then ignore last
    if not stats:
        for lo, _fo, op, r in rows:
            if lo == last:
                stats[op].append(r)
    if not stats:
        for _lo, _fo, op, r in rows:
            stats[op].append(r)
    n_all = sum(len(v) for v in stats.values())
    best_op, best = None, -1e18
    for op in BOILS_STD_OPS:
        xs = stats.get(op) or []
        n = len(xs)
        if n == 0:
            score = 1e9  # unseen
        else:
            mean = sum(xs) / n
            score = mean + c * math.sqrt(math.log(n_all + 1) / n)
        if score > best:
            best, best_op = score, op
    return best_op


def drills_propose(mem: DesignMemory, best_ops: list[str], focus: str) -> dict | None:
    """Append the UCB op to the incumbent sequence."""
    op = ucb_next_op(mem, last=_last_op(best_ops), focus=focus)
    if op is None:
        return None
    seq = [*best_ops, op]
    if len(seq) > 12:
        return None
    return {
        "name": "drills_ucb_" + op.replace(" ", ""),
        "abc_args": [],
        "abc_ops": seq,
        "abc_script": "file",
        "via": "drills_ucb",
        "focus": focus,
    }

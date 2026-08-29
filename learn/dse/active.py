"""Active learning: F3→F5 residual + uncertainty pick the next *level*.

Does not flatten cell / net / cone / F5 knobs into one acquisition vector.
The residual chooses *where* to search; that level keeps its own knobs.

  large |SPEF − ideal|  → interconnect-dominated → net host / net BUF
  small |SPEF − ideal|  → cell/logic delay       → cell host / cell size-up
  n<2 local pairs       → measure the other host  (reduce uncertainty)
"""

from __future__ import annotations

from .acquire import local_hosts
from .memory import DesignMemory
from .surrogate import residual_f3_to_f5_lite, residual_f3_to_f5_local

# SPEF worse than ideal by ≥50 ps → treat as wire-dominated.
WIRE_NS = -0.05


def order_local_hosts(mem: DesignMemory) -> tuple[list, dict]:
    """F3→F5-lite residual reorders cell vs net hosts. Default stays net-first."""
    hosts = list(local_hosts(mem))
    lite = residual_f3_to_f5_lite(list(mem.all()))
    r = lite.get("mean_residual_ns")
    if r is None:
        return hosts, {
            "lite_residual_ns": None,
            "uncertainty": lite.get("uncertainty"),
            "reason": "no F5-lite residual yet — default net then cell",
            "via": "active_f3_to_f5_lite",
        }
    if float(r) >= WIRE_NS:
        hosts = sorted(hosts, key=lambda c: 0 if c.level == "cell" else 1)
        why = (
            f"F3→F5-lite residual {float(r):+.3f} ns (small) — cell host first; "
            "ideal STA is trustworthy, not a mixed knob vector"
        )
    else:
        hosts = sorted(hosts, key=lambda c: 0 if c.level == "net" else 1)
        why = (
            f"F3→F5-lite residual {float(r):+.3f} ns (wire) — net host first; "
            "interconnect dominates, not more ABC"
        )
    return hosts, {
        "lite_residual_ns": float(r),
        "uncertainty": lite.get("uncertainty"),
        "reason": why,
        "via": "active_f3_to_f5_lite",
        "n": lite.get("n"),
    }


def unmeasured_local_hosts(mem: DesignMemory) -> list:
    """Local hosts that do not yet have an F5-local SPEF child."""
    measured = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_local" and c.status == "ok"
    }
    hosts, _ = order_local_hosts(mem)
    return [h for h in hosts if h.id not in measured]


def _latest_f5_local(mem: DesignMemory):
    for c in reversed(list(mem.by_level("routing"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f5_openroad_local":
            return c
    return None


def _spef_path(mem: DesignMemory, child) -> tuple[list[str], list[str]]:
    art = child.artifacts or {}
    cells = [str(x) for x in (art.get("path_cells") or (child.attr or {}).get("cells") or [])]
    hops = [str(x) for x in (art.get("path_nets") or (child.attr or {}).get("nets") or []) if "->" in str(x)]
    sta = art.get("sta") if isinstance(art.get("sta"), dict) else {}
    if not cells:
        cells = [str(x) for x in (sta.get("path_cells") or [])]
    if not hops:
        hops = [str(x) for x in (sta.get("path_nets") or []) if "->" in str(x)]
    return cells, hops


def steer_from_residual(mem: DesignMemory) -> dict | None:
    """Next local action from F3→F5 residual + uncertainty. None if nothing to pay."""
    loc = residual_f3_to_f5_local(list(mem.all()))
    lite = residual_f3_to_f5_lite(list(mem.all()))
    if int(loc.get("n") or 0) < 1:
        return None
    left = unmeasured_local_hosts(mem)
    if left:
        h = left[0]
        return {
            "level": "f5_local",
            "host_id": h.id,
            "host_level": h.level,
            "reason": (
                f"n={loc.get('n')} F3→F5-local pair(s), uncertainty={loc.get('uncertainty')} "
                f"— measure the {h.level} host to cut residual uncertainty, not another ABC"
            ),
            "residual_ns": loc.get("mean_residual_ns"),
            "lite_residual_ns": lite.get("mean_residual_ns"),
            "uncertainty": loc.get("uncertainty"),
            "via": "active_f3_to_f5_residual",
            "not": "a flattened black-box of cell+net+ABC",
        }
    r = loc.get("mean_residual_ns")
    if r is None:
        return None
    child = _latest_f5_local(mem)
    if child is None:
        return None
    cells, hops = _spef_path(mem, child)
    host_id = child.parent_id
    if float(r) < WIRE_NS and hops:
        return {
            "level": "net",
            "host_id": host_id,
            "hops": hops,
            "reason": (
                f"F3→F5-local residual {float(r):+.3f} ns (wire) — BUF on SPEF hops, "
                "not more cell size-up, not a chip restart"
            ),
            "residual_ns": float(r),
            "lite_residual_ns": lite.get("mean_residual_ns"),
            "uncertainty": loc.get("uncertainty"),
            "via": "active_f3_to_f5_residual",
            "not": "a flattened black-box of cell+net+ABC",
        }
    if float(r) >= WIRE_NS and cells:
        return {
            "level": "cell",
            "host_id": host_id,
            "cells": cells,
            "reason": (
                f"F3→F5-local residual {float(r):+.3f} ns (small) — size SPEF-path cells; "
                "ideal STA is trustworthy, not more ABC"
            ),
            "residual_ns": float(r),
            "lite_residual_ns": lite.get("mean_residual_ns"),
            "uncertainty": loc.get("uncertainty"),
            "via": "active_f3_to_f5_residual",
            "not": "a flattened black-box of cell+net+ABC",
        }
    return None

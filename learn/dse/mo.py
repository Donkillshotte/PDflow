"""Multi-objective acquisition on (area, WNS). Physical/PDN knobs never enter.

EHVI is 2-D expected hypervolume improvement (Emmerich-class) with independent
SSK-GP posteriors. It is *not* a scalar that replaces the Pareto front, and it
is never Dynamic IR.
"""

from __future__ import annotations

import random
from typing import Iterable

from .memory import Candidate, DesignMemory


def timing_of(mem: DesignMemory, cand: Candidate) -> tuple[float | None, float | None]:
    """(wns_cost, power_w) from an F3 child or an enriched parent QoR."""
    if cand.qor.wns_cost is not None:
        return float(cand.qor.wns_cost), (
            float(cand.qor.power_w) if cand.qor.power_w is not None else None
        )
    for c in mem.all():
        if c.status != "ok" or (c.knobs or {}).get("source") != "f3_opensta_ideal":
            continue
        if (c.knobs or {}).get("parent_id") == cand.id:
            wns = float(c.qor.wns_cost) if c.qor.wns_cost is not None else None
            pwr = float(c.qor.power_w) if c.qor.power_w is not None else None
            return wns, pwr
    return None, None


def extract_wns(mem: DesignMemory) -> dict[str, float]:
    """Architecture extract name → measured F3 wns_cost."""
    out: dict[str, float] = {}
    for c in mem.by_level("architecture"):
        if c.status != "ok" or c.fidelity != "F1":
            continue
        name = c.knobs.get("extract") or c.knobs.get("name")
        if not name:
            continue
        wns, _ = timing_of(mem, c)
        if wns is not None:
            out[str(name)] = wns
    return out


def baseline_wns(mem: DesignMemory) -> float | None:
    for c in mem.by_level("logic"):
        if c.status != "ok" or c.knobs.get("name") != "liberty_default":
            continue
        wns, _ = timing_of(mem, c)
        if wns is not None:
            return wns
    timed = [timing_of(mem, c)[0] for c in mem.by_level("logic") if c.status == "ok"]
    xs = [w for w in timed if w is not None]
    return min(xs) if xs else None


def logic_mo_rows(mem: DesignMemory) -> list[tuple[list[str], float, float | None, float | None]]:
    """F1 logic rows joined with F3: (abc_ops, area, wns_cost, power_w)."""
    rows = []
    for c in mem.by_level("logic"):
        if c.status != "ok" or c.qor.area_um2 is None:
            continue
        wns, pwr = timing_of(mem, c)
        rows.append((list(c.knobs.get("abc_ops") or []), float(c.qor.area_um2), wns, pwr))
    return rows


def timing_bound(mem: DesignMemory, *, slack_ns: float | None = None) -> bool:
    """True when measured/attributed slack is a real timing deficit (not IR)."""
    wns = baseline_wns(mem)
    if wns is not None:
        return wns > 0.05  # WNS < −50 ps
    if slack_ns is not None:
        return float(slack_ns) < -0.05
    return False


def hypervolume_2d(points: Iterable[tuple[float, float]], ref: tuple[float, float]) -> float:
    """2-D hypervolume for *minimization* vs a worse reference point."""
    raw = [(float(a), float(w)) for a, w in points if a < ref[0] and w < ref[1]]
    if not raw:
        return 0.0
    nd: list[tuple[float, float]] = []
    for p in raw:
        if any(
            q[0] <= p[0] + 1e-15
            and q[1] <= p[1] + 1e-15
            and (q[0] < p[0] - 1e-15 or q[1] < p[1] - 1e-15)
            for q in raw
        ):
            continue
        nd.append(p)
    nd.sort(key=lambda t: (t[0], t[1]))
    uniq: list[tuple[float, float]] = []
    for p in nd:
        if uniq and abs(uniq[-1][0] - p[0]) < 1e-15 and abs(uniq[-1][1] - p[1]) < 1e-15:
            continue
        uniq.append(p)
    hv = 0.0
    xs = [p[0] for p in uniq] + [ref[0]]
    for i, (_x, y) in enumerate(uniq):
        width = xs[i + 1] - uniq[i][0]
        height = ref[1] - y
        if width > 0 and height > 0:
            hv += width * height
    return hv


def _spans(areas: list[float], wns: list[float]) -> tuple[float, float, float, float]:
    a0, a1 = min(areas), max(areas)
    w0, w1 = min(wns), max(wns)
    return a0, max(a1 - a0, 1.0), w0, max(w1 - w0, 0.02)


def _norm(a: float, w: float, spans: tuple[float, float, float, float]) -> tuple[float, float]:
    a0, sa, w0, sw = spans
    return (a - a0) / sa, (w - w0) / sw


def ehvi_2d(
    mu_a: float,
    std_a: float,
    mu_w: float,
    std_w: float,
    front: list[tuple[float, float]],
    *,
    n_mc: int = 48,
    seed: int = 0,
) -> float:
    """Monte-Carlo EHVI on normalized (area, wns_cost). Independent Gaussians."""
    if not front:
        return 0.0
    areas = [p[0] for p in front]
    wns = [p[1] for p in front]
    spans = _spans(areas + [mu_a], wns + [mu_w])
    front_n = [_norm(a, w, spans) for a, w in front]
    ref = (1.25, 1.25)
    base = hypervolume_2d(front_n, ref)
    rng = random.Random(seed)
    sa = max(float(std_a), 1e-9)
    sw = max(float(std_w), 1e-9)
    acc = 0.0
    for _ in range(max(int(n_mc), 8)):
        a = rng.gauss(mu_a, sa)
        w = rng.gauss(mu_w, sw)
        hv = hypervolume_2d(front_n + [_norm(a, w, spans)], ref)
        acc += max(0.0, hv - base)
    return acc / max(int(n_mc), 8)


def ir_of(mem: DesignMemory, cand: Candidate) -> float | None:
    if cand.qor.dynamic_ir_mv is not None:
        return float(cand.qor.dynamic_ir_mv)
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.knobs or {}).get("parent_id") != cand.id:
            continue
        if c.qor.dynamic_ir_mv is not None:
            return float(c.qor.dynamic_ir_mv)
    return None


def mo_scalar(
    area: float,
    wns: float | None,
    *,
    area_ref: float,
    wns_ref: float | None,
    ir_mv: float | None = None,
    ir_ref: float | None = None,
) -> float:
    """Unitless sum of normalized deltas vs a teacher. Lower is better.

    Used only as a *bandit reward*, not as the Pareto ranking.
    """
    sa = (area - area_ref) / max(abs(area_ref), 1.0)
    sw = 0.0
    if wns is not None and wns_ref is not None:
        sw = (wns - wns_ref) / max(abs(wns_ref), 0.02)
    si = 0.0
    if ir_mv is not None and ir_ref is not None:
        si = (ir_mv - ir_ref) / max(abs(ir_ref), 1.0)
    return sa + sw + si

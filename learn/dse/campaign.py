"""Resumable outer DSE campaign: many inner ``run_controller`` passes, one JSONL.

Not a DesignState. Not a flatten of ABC + util + PDN. Each inner run is the
existing layered controller; this module only raises lifetime shot caps,
reuses the same ``DesignMemory``, and stops when gated hypervolume (logic,
area vs ``wns_cost``) stops growing.

``Candidate.pred`` is never a Pareto axis — ranking / tie-break only.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .memory import DesignMemory
from .mo import hypervolume_2d
from .planner import next_candidate_ids, pred_costs

# Per-inner defaults match today's ``Stage.max_shots`` / ``should_pay_*``.
# Inner 0 therefore behaves like a single ``run_controller`` pass.
DEFAULT_SHOTS: dict[str, int] = {
    "f2_fast": 4,
    "gpl": 1,
    "f3": 8,
    "sdf": 1,
    "grt": 1,
    "f5": 1,
    "spef": 1,
    "f5_cts": 1,
    "f5_local": 1,
    "f5_port": 1,
    "synth": 1,
    "cell": 1,
    "net": 1,
    "net_port": 1,
}

InnerRunner = Callable[..., dict]


def lifetime_shots(inner_i: int, base: dict[str, int] | None = None) -> dict[str, int]:
    """Lifetime caps for inner ``inner_i``. ``lifetime_shots(0)`` is ``DEFAULT_SHOTS``."""
    src = dict(DEFAULT_SHOTS)
    if base:
        for k, v in base.items():
            src[str(k)] = int(v)
    bump = max(int(inner_i), 0)
    return {k: int(v) + bump for k, v in src.items()}


def f6_hv_points(mem: DesignMemory) -> list[tuple[float, float]]:
    """Finish (area, wns_cost) pairs. Missing axes dropped. Not logic F3."""
    pts: list[tuple[float, float]] = []
    for c in mem.all():
        if c.status != "ok":
            continue
        if c.fidelity != "F6" and c.level != "signoff":
            continue
        a, w = (c.qor.area_um2 if c.qor else None), (c.qor.wns_cost if c.qor else None)
        if a is None or w is None:
            continue
        pts.append((float(a), float(w)))
    return pts


def gated_hv_f6(mem: DesignMemory, ref: tuple[float, float] | None) -> float:
    if ref is None:
        return 0.0
    pts = f6_hv_points(mem)
    if not pts:
        return 0.0
    return float(hypervolume_2d(pts, ref))


def logic_hv_points(mem: DesignMemory, pred: dict[str, float] | None = None) -> list[tuple[float, float]]:
    """Gated logic front as (area, wns_cost) pairs. Missing axes are dropped."""
    by_id = {c.id: c for c in mem.by_level("logic") if c.status == "ok"}
    pts: list[tuple[float, float]] = []
    for cid in next_candidate_ids(mem, "logic", pred=pred):
        c = by_id.get(cid)
        if c is None:
            continue
        a, w = c.qor.area_um2, c.qor.wns_cost
        if a is None or w is None:
            continue
        pts.append((float(a), float(w)))
    return pts


def suggest_ref(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Freeze a nadir worse than the first non-empty front. Never recompute later."""
    if not points:
        return None
    max_a = max(p[0] for p in points)
    max_w = max(p[1] for p in points)
    return (max_a * 1.5 + 10.0, max_w * 1.5 + 0.1)


def gated_hv(mem: DesignMemory, ref: tuple[float, float] | None, pred: dict[str, float] | None = None) -> float:
    if ref is None:
        return 0.0
    pts = logic_hv_points(mem, pred=pred)
    if not pts:
        return 0.0
    return float(hypervolume_2d(pts, ref))


def _n_src(mem: DesignMemory, source: str, *, level: str | None = None) -> int:
    rows = mem.by_level(level) if level else mem.all()
    return sum(
        1 for c in rows if (c.knobs or {}).get("source") == source and c.status == "ok"
    )


def occupancy(mem: DesignMemory) -> dict[str, int]:
    """Lifetime shot counts that ``lifetime_shots`` raises. Used to resume past spent caps."""
    return {
        "f1": sum(1 for c in mem.all() if c.fidelity == "F1"),
        "f2_fast": sum(
            1
            for c in mem.by_level("physical")
            if (c.knobs or {}).get("source") in ("f2_fast_netgraph", "f2_fast_barycenter")
            and c.status == "ok"
        ),
        "gpl": _n_src(mem, "f2_openroad_gpl", level="physical"),
        "f3": _n_src(mem, "f3_opensta_ideal"),
        "sdf": _n_src(mem, "f3_opensta_sdf_grt"),
        "grt": _n_src(mem, "f2_openroad_grt", level="routing"),
        "f5": _n_src(mem, "f5_openroad_drt_rcx", level="routing"),
        "spef": _n_src(mem, "f3_opensta_spef"),
        "f5_cts": _n_src(mem, "f5_openroad_cts_rcx", level="routing"),
        "f5_local": _n_src(mem, "f5_openroad_local", level="routing"),
        "f5_port": sum(
            1
            for c in mem.by_level("routing")
            if (c.knobs or {}).get("source") == "f5_openroad_local"
            and (c.knobs or {}).get("host_level") == "port"
            and c.status == "ok"
        ),
        "synth": sum(1 for c in mem.all() if c.level == "synthesis" and c.fidelity == "F1"),
        "cell": _n_src(mem, "cell_size_up", level="cell"),
        "net": _n_src(mem, "net_buffer", level="net"),
        "net_port": _n_src(mem, "net_buffer_port", level="net"),
    }


def infer_start_inner(
    mem: DesignMemory,
    *,
    f1_max_per_run: int = 6,
    shots_base: dict[str, int] | None = None,
    max_scan: int = 64,
) -> int:
    """First inner whose lifetime caps still have room. Empty memory → 0."""
    occ = occupancy(mem)
    keys = [k for k in DEFAULT_SHOTS if k != "f1"]
    for i in range(max(int(max_scan), 1)):
        shots = lifetime_shots(i, shots_base)
        f1_max = int(f1_max_per_run) * (i + 1)
        if occ["f1"] < f1_max:
            return i
        if any(occ.get(k, 0) < int(shots[k]) for k in keys):
            return i
    return 0


def _n_ok(mem: DesignMemory) -> int:
    return sum(1 for c in mem.all() if c.status == "ok")


def _wipe(path: Path) -> None:
    if path.is_file():
        path.unlink()
    idx = path.with_suffix(".index.json")
    if idx.is_file():
        idx.unlink()


def _default_inner(**kwargs: Any) -> dict:
    from .controller import run_controller

    return run_controller(**kwargs)


def run_campaign(
    *,
    inner_runner: InnerRunner | None = None,
    memory_path: Path,
    wall_s: float,
    hv_eps: float = 1e-3,
    max_inner: int = 8,
    inner_budget_s: float = 45.0,
    f1_max_per_run: int = 6,
    variant: str = "flowlab",
    design_id: str = "gcd",
    rtl: Path | None = None,
    fresh: bool = False,
    arch_max: int = 3,
    shots_base: dict[str, int] | None = None,
    start_inner: int | None = None,
    stop_metric: str = "logic",
) -> dict:
    """Loop ``inner_runner`` (default ``run_controller``) on one JSONL until HV stalls.

    Stop: ``hv_eps`` (relative gain vs previous inner, skipped while prev HV is 0),
    ``wall`` (total wall budget), ``zero_new`` (inner added no new ``ok`` rows),
    ``max_inner``.
    """
    path = Path(memory_path)
    runner = inner_runner or _default_inner
    inners: list[dict] = []
    ref: tuple[float, float] | None = None
    prev_hv = 0.0
    stop = "max_inner"
    n_inner = 0

    if float(wall_s) <= 0.0:
        return {
            "ok": True,
            "stop": "wall",
            "n_inner": 0,
            "hv": [],
            "ref": None,
            "memory": str(path),
            "inners": [],
        }

    if fresh:
        _wipe(path)

    mem0 = DesignMemory(path)
    pred0 = pred_costs(mem0) or None
    if str(stop_metric) == "f6":
        pts0 = f6_hv_points(mem0)
        if pts0:
            ref = suggest_ref(pts0)
            prev_hv = gated_hv_f6(mem0, ref)
    else:
        pts0 = logic_hv_points(mem0, pred=pred0)
        if pts0:
            ref = suggest_ref(pts0)
            prev_hv = gated_hv(mem0, ref, pred=pred0)
    first = int(start_inner) if start_inner is not None else infer_start_inner(
        mem0, f1_max_per_run=f1_max_per_run, shots_base=shots_base
    )
    first = max(first, 0)

    t_end = time.time() + float(wall_s)
    n_cap = max(int(max_inner), 0)
    for k in range(n_cap):
        inner_i = first + k
        if time.time() >= t_end:
            stop = "wall"
            break
        left = t_end - time.time()
        inner_s = min(float(inner_budget_s), max(left, 0.0))
        if inner_s <= 0.0:
            stop = "wall"
            break
        mem = DesignMemory(path)
        n_before = _n_ok(mem)
        shots = lifetime_shots(inner_i, shots_base)
        f1_max = int(f1_max_per_run) * (inner_i + 1)
        runner(
            variant=variant,
            budget_s=inner_s,
            f1_max=f1_max,
            design_id=design_id,
            rtl=rtl,
            memory_path=path,
            fresh=False,
            arch_max=arch_max,
            max_shots=shots,
        )
        mem = DesignMemory(path)
        pred = pred_costs(mem) or None
        if str(stop_metric) == "f6":
            pts = f6_hv_points(mem)
            if ref is None and pts:
                ref = suggest_ref(pts)
            hv = gated_hv_f6(mem, ref)
        else:
            pts = logic_hv_points(mem, pred=pred)
            if ref is None and pts:
                ref = suggest_ref(pts)
            hv = gated_hv(mem, ref, pred=pred)
        n_after = _n_ok(mem)
        n_new = n_after - n_before
        inners.append(
            {
                "inner": inner_i,
                "n_ok": n_after,
                "n_new": n_new,
                "hv": hv,
                "f1_max": f1_max,
                "max_shots": dict(shots),
            }
        )
        n_inner += 1
        if n_new <= 0:
            stop = "zero_new"
            break
        if prev_hv > 0.0 and (hv - prev_hv) / prev_hv < float(hv_eps):
            stop = "hv_eps"
            break
        prev_hv = hv
        if time.time() >= t_end:
            stop = "wall"
            break
    else:
        if n_inner >= n_cap:
            stop = "max_inner"

    return {
        "ok": True,
        "stop": stop,
        "n_inner": n_inner,
        "start_inner": first,
        "hv": [row["hv"] for row in inners],
        "ref": list(ref) if ref else None,
        "memory": str(path),
        "inners": inners,
    }

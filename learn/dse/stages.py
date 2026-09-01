"""Declarative DSE stages. Depth/level is data; the controller calls run_stage.

Strangler: one lotto of stages at a time. ``why`` / ``step`` strings stay
identical to the inlined controller blocks they replace. F4 stages set
``needs_admit=True`` (passo 3d).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .ir_champ import run_ir_champ_family
from .ir_inspect import run_ir_inspect_loops
from .ir_region_cell import run_winning_ir_region_cell
from .ir_solvers import run_ir_solvers


def shot_cap(ctx: dict, key: str, default: int) -> int:
    """Lifetime shot cap from ``ctx['max_shots']``; missing keys keep today's default."""
    shots = ctx.get("max_shots")
    if isinstance(shots, dict) and key in shots:
        return int(shots[key])
    return int(default)


def _mapped_new_parent(ctx: dict, cands, *, level: str, source: str):
    """``mapped_pick`` after skipping parents that already have this child.

    ``pred_by_id`` reorders only when non-empty so the first inner keeps
    today's area-winner-first order.
    """
    from .planner import have_child_parents, parent_queue

    queue = parent_queue(
        cands,
        have_child_ids=have_child_parents(ctx["mem"], level=level, source=source),
        pred_by_id=ctx.get("pred_by_id") or None,
    )
    return ctx["mapped_pick"](
        queue, rtl=ctx["rtl"], liberty=ctx["liberty"], top=ctx["top"]
    )


def should_pay_generic(
    *,
    budget_left: float | None = None,
    n_have: int = 0,
    max_shots: int = 1,
    min_s: float = 0.0,
    parents_ok: bool = True,
    exhausted_why: str,
    budget_why: str,
    no_parent_why: str,
    ok_why: str,
) -> tuple[bool, str]:
    """Common n_have / wall / parent gate. Domain checks stay in the caller."""
    if n_have >= max_shots:
        return False, exhausted_why
    if budget_left is not None and budget_left < min_s:
        return False, budget_why
    if not parents_ok:
        return False, no_parent_why
    return True, ok_why


def planned(plan: dict, level: str) -> bool:
    return any(s.get("level") == level for s in (plan.get("steps") or []))


@dataclass
class Stage:
    level: str
    run: Callable[[dict], bool]
    acquire_fidelity: str | None = None
    cost_key: str | None = None
    max_shots: int = 1
    min_s: float = 0.0
    needs_admit: bool = False


def run_stage(stage: Stage, ctx: dict[str, Any]) -> bool:
    """Pay at most this stage. ``stage.run`` owns should_pay + evaluate.

    F4 stages set ``needs_admit=True``; ``_pay_and_maybe_eval`` then calls
    ``ctx["admit_paid_f4"]`` before evaluate (passo 3d / passo 2).
    """
    bound = dict(ctx)
    bound["_stage"] = stage
    return bool(stage.run(bound))


def _pay_and_maybe_eval(
    ctx: dict,
    *,
    level: str,
    acquire_fidelity: str | None,
    pay: bool,
    why: str,
    evaluate: Callable[[], bool],
    cost_key: str | None = None,
    fidelity: str | None = None,
    acquire_extra: dict | None = None,
    require_plan: bool = True,
) -> bool:
    step = ctx["step"]
    plan = ctx["plan"]
    t_end = ctx["t_end"]
    mem = ctx["mem"]
    if acquire_fidelity:
        extra = dict(acquire_extra or {})
        step("acquire", fidelity=acquire_fidelity, pay=pay, why=why, **extra)
    plan_ok = planned(plan, level) if require_plan else True
    if not plan_ok or not pay or time.time() >= t_end:
        return False
    if cost_key:
        from .costs import estimated_cost_s

        est = estimated_cost_s(
            mem,
            fidelity or acquire_fidelity or "F1",
            ctx["design_id"],
            cost_key=cost_key,
        )
        if time.time() + est > t_end:
            return False
    stage = ctx.get("_stage")
    if stage is not None and getattr(stage, "needs_admit", False):
        admit = ctx.get("admit_paid_f4")
        if callable(admit):
            gate = admit(
                mem,
                solver=ctx.get("admit_solver") or "direct",
                n_r=ctx.get("admit_n_r"),
                n_nodes=ctx.get("admit_n_nodes"),
                extract_id=ctx.get("admit_extract_id"),
                extract_hit=ctx.get("admit_extract_hit"),
                spice=ctx.get("admit_spice"),
                step=step,
                variant=ctx.get("variant") or "flowlab",
                design_id=ctx["design_id"],
            )
            if not gate.get("admitted"):
                return False
    return evaluate()


def run_f2_fast(ctx: dict) -> bool:
    from .acquire import should_pay_f2_fast
    from .fidelity import evaluate_f2_fast

    mem = ctx["mem"]
    f2_max = shot_cap(ctx, "f2_fast", 4)
    n_f2 = sum(
        1
        for c in mem.by_level("physical")
        if (c.knobs or {}).get("source") in ("f2_fast_netgraph", "f2_fast_barycenter")
        and c.status == "ok"
    )
    pay, why = should_pay_f2_fast(mem, n_f2=n_f2, f2_max=f2_max)

    def _eval() -> bool:
        nonlocal n_f2
        from .planner import have_child_parents, parent_queue

        winners = list(ctx["f1_pareto_parents"](mem))
        seen = {c.id for c in winners}
        extra = [c for c in ctx["f1_ok"](mem) if c.id not in seen]
        extra.sort(key=lambda c: float(c.qor.area_um2))
        winners.extend(extra)
        winners = parent_queue(
            winners,
            have_child_ids=have_child_parents(
                mem, level="physical", source=("f2_fast_netgraph", "f2_fast_barycenter")
            ),
            pred_by_id=ctx.get("pred_by_id") or None,
        )
        paid = False
        for w in winners:
            if n_f2 >= f2_max or time.time() >= ctx["t_end"]:
                break
            w = ctx["ensure_mapped_netlist"](w, rtl=ctx["rtl"], liberty=ctx["liberty"], top=ctx["top"])
            mem.touch(w)
            child = evaluate_f2_fast(w, mem, design_id=ctx["design_id"])
            if child:
                n_f2 += 1
                paid = True
                ctx["step"](
                    "evaluate",
                    id=child.id,
                    level="physical",
                    fidelity="F2",
                    via="f2_fast_netgraph",
                    parent=w.id,
                    hpwl=(child.artifacts or {}).get("hpwl"),
                    congestion=child.qor.congestion,
                )
        return paid

    return _pay_and_maybe_eval(
        ctx, level="f2_fast", acquire_fidelity=None, pay=pay, why=why, evaluate=_eval,
        cost_key="F2_FAST", fidelity="F2",
    )


def run_f2_gpl(ctx: dict) -> bool:
    from .acquire import should_pay_f2_gpl
    from .costs import estimated_cost_s
    from .fidelity import evaluate_f2_gpl

    mem = ctx["mem"]
    n_gpl = sum(
        1
        for c in mem.by_level("physical")
        if (c.knobs or {}).get("source") == "f2_openroad_gpl" and c.status == "ok"
    )
    min_s = estimated_cost_s(mem, "F2", ctx["design_id"], cost_key="F2_GPL")
    gpl_max = shot_cap(ctx, "gpl", 1)
    pay, why = should_pay_f2_gpl(
        mem, budget_left=ctx["t_end"] - time.time(), n_gpl=n_gpl, gpl_max=gpl_max, min_s=min_s
    )

    def _eval() -> bool:
        pick = _mapped_new_parent(
            ctx,
            [ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            level="physical",
            source="f2_openroad_gpl",
        )
        if not pick:
            return False
        mem.touch(pick)
        params = ctx["flowlab_params"]()
        util0 = float(params.get("coreUtilization") or 35.0)
        den0 = ctx["gpl_density"](util0, params.get("placeDensityAddon") or 0.2)
        child = evaluate_f2_gpl(pick, mem, design_id=ctx["design_id"], util=util0, density=den0)
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="physical",
            fidelity="F2",
            via="f2_openroad_gpl",
            parent=pick.id,
            hpwl_um=(child.artifacts or {}).get("hpwl_um"),
            overflow=child.qor.congestion,
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f2_gpl", acquire_fidelity="F2_GPL", pay=pay, why=why, evaluate=_eval,
        cost_key="F2_GPL", fidelity="F2",
    )


def run_f3_sta(ctx: dict) -> bool:
    from .acquire import should_pay_f3_sta
    from .costs import estimated_cost_s
    from .fidelity import evaluate_f3_sta

    mem = ctx["mem"]
    n_sta = sum(
        1 for c in mem.all() if (c.knobs or {}).get("source") == "f3_opensta_ideal" and c.status == "ok"
    )
    min_s = estimated_cost_s(mem, "F3", ctx["design_id"], cost_key="F3")
    sta_max = shot_cap(ctx, "f3", 8)
    pay, why = should_pay_f3_sta(
        mem, budget_left=ctx["t_end"] - time.time(), n_sta=n_sta, sta_max=sta_max, min_s=min_s
    )

    def _eval() -> bool:
        from .planner import have_child_parents, parent_queue

        ranked = [
            c
            for c in mem.all()
            if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None
        ]
        ranked.sort(key=lambda c: float(c.qor.area_um2))
        ranked = parent_queue(
            ranked,
            have_child_ids=have_child_parents(mem, source="f3_opensta_ideal"),
            pred_by_id=ctx.get("pred_by_id") or None,
        )
        paid = False
        remain = max(int(sta_max) - n_sta, 0)
        for w in ranked[: min(4, remain)]:
            if time.time() >= ctx["t_end"]:
                break
            w = ctx["ensure_mapped_netlist"](w, rtl=ctx["rtl"], liberty=ctx["liberty"], top=ctx["top"])
            mem.touch(w)
            child = evaluate_f3_sta(w, mem, design_id=ctx["design_id"])
            if child:
                paid = True
                ctx["step"](
                    "evaluate",
                    id=child.id,
                    level=w.level,
                    fidelity="F3",
                    via="f3_opensta_ideal",
                    parent=w.id,
                    wns_ns=(child.artifacts or {}).get("wns_ns"),
                    power_w=child.qor.power_w,
                    status=child.status,
                )
        return paid

    return _pay_and_maybe_eval(
        ctx, level="f3_sta", acquire_fidelity="F3", pay=pay, why=why, evaluate=_eval,
        cost_key="F3", fidelity="F3",
    )


def run_f3_sdf(ctx: dict) -> bool:
    from .acquire import should_pay_f3_sdf
    from .costs import estimated_cost_s
    from .fidelity import evaluate_f3_sdf

    mem = ctx["mem"]
    n_sdf = sum(
        1
        for c in mem.all()
        if (c.knobs or {}).get("source") == "f3_opensta_sdf_grt" and c.status == "ok"
    )
    min_s = estimated_cost_s(mem, "F3", ctx["design_id"], cost_key="F3_SDF")
    sdf_max = shot_cap(ctx, "sdf", 1)
    pay, why = should_pay_f3_sdf(
        mem, budget_left=ctx["t_end"] - time.time(), n_sdf=n_sdf, sdf_max=sdf_max, min_s=min_s
    )

    def _eval() -> bool:
        host = next(
            (
                c
                for c in mem.all()
                if (c.artifacts or {}).get("sdf")
                and (c.artifacts or {}).get("mapped_v")
                and Path(c.artifacts["sdf"]).is_file()
                and Path(c.artifacts["mapped_v"]).is_file()
            ),
            None,
        )
        if not host:
            return False
        sdfc = evaluate_f3_sdf(host, mem, design_id=ctx["design_id"])
        if not sdfc:
            return False
        ctx["step"](
            "evaluate",
            id=sdfc.id,
            level=host.level,
            fidelity="F3",
            via="f3_opensta_sdf_grt",
            parent=host.id,
            wns_ns=(sdfc.artifacts or {}).get("wns_ns"),
            interconnect="sdf_grt",
            status=sdfc.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f3_sdf", acquire_fidelity="F3_SDF", pay=pay, why=why, evaluate=_eval,
        cost_key="F3_SDF", fidelity="F3",
    )


def run_routing(ctx: dict) -> bool:
    from .acquire import should_pay_f2_grt
    from .costs import estimated_cost_s
    from .fidelity import evaluate_f2_grt

    mem = ctx["mem"]
    n_grt = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f2_openroad_grt" and c.status == "ok"
    )
    min_s = estimated_cost_s(mem, "F2", ctx["design_id"], cost_key="F2_GRT")
    grt_max = shot_cap(ctx, "grt", 1)
    pay, why = should_pay_f2_grt(
        mem, budget_left=ctx["t_end"] - time.time(), n_grt=n_grt, grt_max=grt_max, min_s=min_s
    )

    def _eval() -> bool:
        pick = _mapped_new_parent(
            ctx,
            [ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            level="routing",
            source="f2_openroad_grt",
        )
        if not pick:
            return False
        mem.touch(pick)
        child = evaluate_f2_grt(pick, mem, design_id=ctx["design_id"])
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="routing",
            fidelity="F2",
            via="f2_openroad_grt",
            parent=pick.id,
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            overflow=child.qor.congestion,
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="routing", acquire_fidelity="F2_GRT", pay=pay, why=why, evaluate=_eval,
        cost_key="F2_GRT", fidelity="F2",
    )


def run_f5_drt(ctx: dict) -> bool:
    from .acquire import should_pay_f5_drt
    from .costs import estimated_cost_s
    from .fidelity import evaluate_f5_drt

    mem = ctx["mem"]
    n_f5 = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_drt_rcx" and c.status == "ok"
    )
    min_s = estimated_cost_s(mem, "F5", ctx["design_id"], cost_key="F5")
    f5_max = shot_cap(ctx, "f5", 1)
    pay, why = should_pay_f5_drt(
        mem, budget_left=ctx["t_end"] - time.time(), n_f5=n_f5, f5_max=f5_max, min_s=min_s
    )

    def _eval() -> bool:
        pick = _mapped_new_parent(
            ctx,
            [ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            level="routing",
            source="f5_openroad_drt_rcx",
        )
        if not pick:
            return False
        mem.touch(pick)
        child = evaluate_f5_drt(pick, mem, design_id=ctx["design_id"])
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="routing",
            fidelity="F5",
            via="f5_openroad_drt_rcx",
            parent=pick.id,
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            n_rc=(child.artifacts or {}).get("n_rc_segments"),
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f5_drt", acquire_fidelity="F5", pay=pay, why=why, evaluate=_eval,
        cost_key="F5", fidelity="F5",
    )


def run_f3_spef(ctx: dict) -> bool:
    from pathlib import Path

    from .acquire import should_pay_f3_spef
    from .costs import estimated_cost_s
    from .fidelity import evaluate_f3_spef

    mem = ctx["mem"]
    n_spef = sum(
        1 for c in mem.all() if (c.knobs or {}).get("source") == "f3_opensta_spef" and c.status == "ok"
    )
    min_s = estimated_cost_s(mem, "F3", ctx["design_id"], cost_key="F3")
    spef_max = shot_cap(ctx, "spef", 1)
    pay, why = should_pay_f3_spef(
        mem, budget_left=ctx["t_end"] - time.time(), n_spef=n_spef, spef_max=spef_max, min_s=min_s
    )

    def _eval() -> bool:
        host = next(
            (
                c
                for c in mem.all()
                if (c.artifacts or {}).get("spef")
                and (c.artifacts or {}).get("mapped_v")
                and Path(c.artifacts["spef"]).is_file()
                and Path(c.artifacts["mapped_v"]).is_file()
            ),
            None,
        )
        if not host:
            return False
        spc = evaluate_f3_spef(host, mem, design_id=ctx["design_id"])
        if not spc:
            return False
        ctx["step"](
            "evaluate",
            id=spc.id,
            level=host.level,
            fidelity="F3",
            via="f3_opensta_spef",
            parent=host.id,
            wns_ns=(spc.artifacts or {}).get("wns_ns"),
            interconnect="spef",
            status=spc.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f3_spef", acquire_fidelity="F3_SPEF", pay=pay, why=why, evaluate=_eval,
        cost_key="F3", fidelity="F3",
    )


def run_f5_cts(ctx: dict) -> bool:
    from .acquire import should_pay_f5_cts
    from .costs import estimated_cost_s
    from .fidelity import evaluate_f5_cts

    mem = ctx["mem"]
    n_f5_cts = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_cts_rcx" and c.status == "ok"
    )
    min_s = estimated_cost_s(mem, "F5", ctx["design_id"], cost_key="F5_CTS")
    f5_cts_max = shot_cap(ctx, "f5_cts", 1)
    pay, why = should_pay_f5_cts(
        mem,
        budget_left=ctx["t_end"] - time.time(),
        n_f5_cts=n_f5_cts,
        f5_cts_max=f5_cts_max,
        min_s=min_s,
    )

    def _eval() -> bool:
        pick = _mapped_new_parent(
            ctx,
            [ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            level="routing",
            source="f5_openroad_cts_rcx",
        )
        if not pick:
            return False
        mem.touch(pick)
        child = evaluate_f5_cts(pick, mem, design_id=ctx["design_id"])
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="routing",
            fidelity="F5",
            via="f5_openroad_cts_rcx",
            parent=pick.id,
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            n_clkbuf=(child.artifacts or {}).get("n_clkbuf"),
            clock="propagated",
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f5_cts", acquire_fidelity="F5_CTS", pay=pay, why=why, evaluate=_eval,
        cost_key="F5_CTS", fidelity="F5",
    )


def run_f5_local(ctx: dict) -> bool:
    from .acquire import should_pay_f5_local
    from .active import order_local_hosts
    from .costs import estimated_cost_s
    from .fidelity import evaluate_f5_local

    mem = ctx["mem"]
    n_f5_local = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_local" and c.status == "ok"
    )
    min_s = estimated_cost_s(mem, "F5", ctx["design_id"], cost_key="F5")
    f5_local_max = shot_cap(ctx, "f5_local", 1)
    pay, why = should_pay_f5_local(
        mem,
        budget_left=ctx["t_end"] - time.time(),
        n_f5_local=n_f5_local,
        f5_local_max=f5_local_max,
        min_s=min_s,
    )
    hosts_ord, host_why = order_local_hosts(mem)

    def _eval() -> bool:
        from .acquire import local_hosts
        from .planner import have_child_parents, parent_queue

        child = None
        host = None
        hosts = parent_queue(
            hosts_ord or local_hosts(mem),
            have_child_ids=have_child_parents(mem, level="routing", source="f5_openroad_local"),
            pred_by_id=ctx.get("pred_by_id") or None,
        )
        for cand in hosts:
            mem.touch(cand)
            child = evaluate_f5_local(cand, mem, design_id=ctx["design_id"])
            host = cand
            if child and child.status == "ok":
                break
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="routing",
            fidelity="F5",
            via="f5_openroad_local",
            parent=host.id if host else None,
            host_level=host.level if host else None,
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            ideal_wns_ns=(child.artifacts or {}).get("ideal_wns_ns"),
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f5_local", acquire_fidelity="F5_LOCAL", pay=pay, why=why, evaluate=_eval,
        cost_key="F5", fidelity="F5", acquire_extra=host_why,
    )


def run_f5_port(ctx: dict) -> bool:
    from .acquire import latest_port_host, should_pay_f5_port
    from .costs import estimated_cost_s
    from .fidelity import evaluate_f5_local

    mem = ctx["mem"]
    n_f5_port = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_local"
        and (c.knobs or {}).get("host_level") == "port"
        and c.status == "ok"
    )
    min_s = estimated_cost_s(mem, "F5", ctx["design_id"], cost_key="F5")
    f5_port_max = shot_cap(ctx, "f5_port", 1)
    pay, why = should_pay_f5_port(
        mem,
        budget_left=ctx["t_end"] - time.time(),
        n_f5_port=n_f5_port,
        f5_port_max=f5_port_max,
        min_s=min_s,
    )

    def _eval() -> bool:
        host = latest_port_host(mem)
        if not host:
            return False
        mem.touch(host)
        child = evaluate_f5_local(host, mem, design_id=ctx["design_id"])
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="routing",
            fidelity="F5",
            via="f5_openroad_local",
            parent=host.id,
            host_level="port",
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            ideal_wns_ns=(child.artifacts or {}).get("ideal_wns_ns"),
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f5_port", acquire_fidelity="F5_PORT", pay=pay, why=why, evaluate=_eval,
        cost_key="F5", fidelity="F5",
    )


def run_synthesis(ctx: dict) -> bool:
    from .acquire import should_pay_f1_synth
    from .fidelity import evaluate_f1_synth

    mem = ctx["mem"]
    n_f1 = sum(1 for c in mem.all() if c.fidelity == "F1")
    pay, why = should_pay_f1_synth(
        mem,
        budget_left=ctx["t_end"] - time.time(),
        n_f1=n_f1,
        f1_max=ctx["f1_max"],
        synth_max=shot_cap(ctx, "synth", 1),
    )

    def _eval() -> bool:
        ctx["step"](
            "propose",
            level="synthesis",
            knobs={"name": "orfs_abc_speed", "abcArea": 0, "source": "orfs_abc_script"},
            fidelity="F1",
            why=why,
        )
        phys = ctx.get("phys")
        cand = evaluate_f1_synth(
            rtl=ctx["rtl"],
            liberty=ctx["liberty"],
            mem=mem,
            design_id=ctx["design_id"],
            parent_id=phys.id if phys else None,
            top=ctx["top"],
        )
        attr = ctx.get("attr") or {}
        if attr.get("status") == "READY":
            cand.attr = {
                "inherited_from": "physical_ir",
                "scope": "chip",
                "transform": "orfs_abc_speed",
                "note": "synthesis F1 is ORFS abc_speed.script; not flattened into BOiLS abc_ops",
            }
        mem.touch(cand)
        ctx["step"](
            "evaluate",
            id=cand.id,
            level="synthesis",
            fidelity="F1",
            status=cand.status,
            area_um2=cand.qor.area_um2,
            cost_s=cand.cost_s,
            via="orfs_abc_speed",
        )
        ctx["time_candidate"](cand, reason="F3 after ORFS abc_speed so WNS can compare to liberty_default")
        return True

    return _pay_and_maybe_eval(
        ctx, level="synthesis", acquire_fidelity="F1_SYNTH", pay=pay, why=why, evaluate=_eval,
        cost_key="F1", fidelity="F1",
    )


def run_cell(ctx: dict) -> bool:
    from .acquire import should_pay_cell_size
    from .fidelity import evaluate_cell_size

    mem = ctx["mem"]
    n_cell = sum(
        1 for c in mem.by_level("cell") if (c.knobs or {}).get("source") == "cell_size_up" and c.status == "ok"
    )
    cell_max = shot_cap(ctx, "cell", 1)
    pay, why = should_pay_cell_size(
        mem, budget_left=ctx["t_end"] - time.time(), n_cell=n_cell, cell_max=cell_max
    )

    def _eval() -> bool:
        pick = _mapped_new_parent(
            ctx,
            [ctx["f1_wns_winner"](mem), ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            level="cell",
            source="cell_size_up",
        )
        if not pick:
            return False
        mem.touch(pick)
        child = evaluate_cell_size(pick, mem, design_id=ctx["design_id"])
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="cell",
            fidelity="F3",
            via="cell_size_up",
            parent=pick.id,
            n_changed=(child.artifacts or {}).get("n_changed"),
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            area_um2=child.qor.area_um2,
            status=child.status,
            reason="attributed-path-drive-up",
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="cell", acquire_fidelity="CELL_SIZE", pay=pay, why=why, evaluate=_eval,
        cost_key="F3", fidelity="F3",
    )


def run_net(ctx: dict) -> bool:
    from .acquire import should_pay_net_buffer
    from .fidelity import evaluate_net_buffer

    mem = ctx["mem"]
    n_net = sum(
        1 for c in mem.by_level("net") if (c.knobs or {}).get("source") == "net_buffer" and c.status == "ok"
    )
    net_max = shot_cap(ctx, "net", 1)
    pay, why = should_pay_net_buffer(
        mem, budget_left=ctx["t_end"] - time.time(), n_net=n_net, net_max=net_max
    )

    def _eval() -> bool:
        from .planner import have_child_parents

        have = have_child_parents(mem, level="net", source="net_buffer")
        pick = next(
            (
                c
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok"
                and (c.artifacts or {}).get("mapped_v")
                and c.id not in have
            ),
            None,
        )
        if pick is None:
            pick = _mapped_new_parent(
                ctx,
                [ctx["f1_wns_winner"](mem), ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
                level="net",
                source="net_buffer",
            )
        if not pick:
            return False
        mem.touch(pick)
        child = evaluate_net_buffer(pick, mem, design_id=ctx["design_id"])
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="net",
            fidelity="F3",
            via="net_buffer",
            parent=pick.id,
            n_changed=(child.artifacts or {}).get("n_changed"),
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            area_um2=child.qor.area_um2,
            status=child.status,
            reason="attributed-path-net-buffer",
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="net", acquire_fidelity="NET_BUF", pay=pay, why=why, evaluate=_eval,
        cost_key="F3", fidelity="F3",
    )


def run_net_port(ctx: dict) -> bool:
    import re
    from pathlib import Path

    from .acquire import _attributed_cross_module_nets, should_pay_net_port
    from .fidelity import evaluate_net_port_buffer

    mem = ctx["mem"]
    n_net = sum(
        1 for c in mem.by_level("net") if (c.knobs or {}).get("source") == "net_buffer" and c.status == "ok"
    )
    n_port = sum(
        1
        for c in mem.by_level("net")
        if (c.knobs or {}).get("source") == "net_buffer_port" and c.status == "ok"
    )
    port_max = shot_cap(ctx, "net_port", 1)
    pay, why = should_pay_net_port(
        mem,
        budget_left=ctx["t_end"] - time.time(),
        n_net=n_net,
        n_port=n_port,
        port_max=port_max,
    )

    def _eval() -> bool:
        pick = None
        for cand in list(mem.by_level("net"))[::-1] + list(mem.by_level("cell"))[::-1] + [
            c for c in ctx["f1_ok"](mem)
        ]:
            if cand is None or cand.status != "ok":
                continue
            hier = (cand.artifacts or {}).get("mapped_hier_v")
            mapped = (cand.artifacts or {}).get("mapped_v")
            if hier and Path(hier).is_file():
                pick = cand
                break
            if mapped and Path(mapped).is_file():
                try:
                    body = Path(mapped).read_text()
                except OSError:
                    body = ""
                if len(re.findall(r"(?m)^module\s", body)) >= 3:
                    pick = cand
                    break
        if pick is None:
            pick = ctx["mapped_pick"](
                [ctx["f1_wns_winner"](mem), ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
                rtl=ctx["rtl"],
                liberty=ctx["liberty"],
            )
        if not pick:
            return False
        mem.touch(pick)
        child = evaluate_net_port_buffer(
            pick,
            mem,
            design_id=ctx["design_id"],
            hops=_attributed_cross_module_nets(mem),
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="net",
            fidelity="F3",
            via="net_buffer_port",
            parent=pick.id,
            n_changed=(child.artifacts or {}).get("n_changed"),
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            area_um2=child.qor.area_um2,
            status=child.status,
            reason="attributed-path-port-net-buffer",
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="net_port", acquire_fidelity="NET_PORT", pay=pay, why=why, evaluate=_eval,
        cost_key="F3", fidelity="F3",
    )


def run_physical_catalog(ctx: dict) -> bool:
    from .acquire import should_pay_physical_catalog
    from .fidelity import evaluate_f2_gpl
    from .physical_space import next_catalog_spec, propose_physical_f0

    mem = ctx["mem"]
    phys_f0 = propose_physical_f0(mem, ctx["design_id"])
    for c in phys_f0:
        ctx["step"]("propose", level="physical", knobs=c.knobs, fidelity="F0")
    n_cat = sum(1 for c in mem.by_level("physical") if (c.knobs or {}).get("catalog"))
    pay, why = should_pay_physical_catalog(
        mem, budget_left=ctx["t_end"] - time.time(), n_catalog=n_cat
    )
    spec = next_catalog_spec(mem) if pay else None

    def _eval() -> bool:
        if not spec:
            return False
        pick = ctx["mapped_pick"](
            [ctx["f1_wns_winner"](mem), ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            rtl=ctx["rtl"],
            liberty=ctx["liberty"],
            top=ctx["top"],
        )
        if not pick:
            return False
        mem.touch(pick)
        util_c = float(spec["coreUtilization"])
        den_c = ctx["gpl_density"](util_c, spec["placeDensityAddon"])
        child = evaluate_f2_gpl(
            pick,
            mem,
            design_id=ctx["design_id"],
            util=util_c,
            density=den_c,
            extra_knobs={
                "catalog": spec["name"],
                "coreUtilization": spec["coreUtilization"],
                "placeDensityAddon": spec["placeDensityAddon"],
            },
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="physical",
            fidelity="F2",
            via="f2_openroad_gpl_catalog",
            parent=pick.id,
            catalog=spec["name"],
            hpwl_um=(child.artifacts or {}).get("hpwl_um"),
            overflow=child.qor.congestion,
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx,
        level="physical_catalog",
        acquire_fidelity="F2_GPL_CATALOG",
        pay=pay,
        why=why,
        evaluate=_eval,
        cost_key="F2_GPL",
        fidelity="F2",
        require_plan=False,
    )


def _latest_extract(ctx: dict):
    mem = ctx["mem"]
    hit = ctx["latest_ok_extract"](mem)
    extract_id = str(hit["extract_id"]) if hit else "finish"
    return hit, extract_id


def _set_admit(ctx: dict, *, solver: str, extract_id: str | None = None, extract_hit=None, spice=None, n_r=None):
    ctx["admit_solver"] = solver
    ctx["admit_extract_id"] = extract_id
    ctx["admit_extract_hit"] = extract_hit
    ctx["admit_spice"] = spice
    ctx["admit_n_r"] = n_r
    if extract_hit and n_r is None:
        cand = extract_hit.get("candidate") if isinstance(extract_hit, dict) else None
        art = (cand.artifacts if cand is not None else {}) or {}
        if art.get("n_r") is not None:
            ctx["admit_n_r"] = int(art["n_r"])
        elif extract_hit.get("n_r") is not None:
            ctx["admit_n_r"] = int(extract_hit["n_r"])


def run_f4_extract(ctx: dict) -> bool:
    from .acquire import should_pay_f4_extract

    mem = ctx["mem"]
    n_ext = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_candidate_extract" and c.status == "ok"
    )
    pay, why = should_pay_f4_extract(
        mem, budget_left=ctx["t_end"] - time.time(), n_extract=n_ext
    )
    _set_admit(ctx, solver="direct")

    def _eval() -> bool:
        prefer = []
        base_p_ext = None
        for c in mem.by_level("logic"):
            if c.status == "ok" and c.knobs.get("name") == "liberty_default":
                _w, p = ctx["timing_of"](mem, c)
                if p:
                    base_p_ext = p
                    break
        if base_p_ext:
            for cand in (ctx["f1_wns_winner"](mem), ctx["f1_area_winner"](mem), *ctx["f1_ok"](mem)):
                if cand is None:
                    continue
                _w, p = ctx["timing_of"](mem, cand)
                if p is None or abs(float(p) / float(base_p_ext) - 1.0) < 0.03:
                    continue
                prefer.append(cand)
                break
        pick = ctx["mapped_pick"](
            prefer + [ctx["f1_wns_winner"](mem), ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            rtl=ctx["rtl"],
            liberty=ctx["liberty"],
            top=ctx["top"],
        )
        if not pick:
            return False
        mem.touch(pick)
        params = ctx["flowlab_params"]()
        util_e = float(params.get("coreUtilization") or 35.0)
        den_e = ctx["gpl_density"](util_e, params.get("placeDensityAddon") or 0.2)
        child = ctx["evaluate_f4_extract"](
            pick,
            mem,
            design_id=ctx["design_id"],
            variant=ctx["variant"],
            util=util_e,
            density=den_e,
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="f4_candidate_extract",
            parent=pick.id,
            n_r=(child.artifacts or {}).get("n_r"),
            droop_mv=child.qor.dynamic_ir_mv,
            em_j=(child.qor.em_j_a_m2),
            gold=False,
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f4_extract", acquire_fidelity="F4_EXTRACT", pay=pay, why=why, evaluate=_eval,
        cost_key="F4_EXTRACT", fidelity="F4",
    )


def run_f4_region_extract(ctx: dict) -> bool:
    from .acquire import should_pay_f4_region_extract

    mem = ctx["mem"]
    attr = ctx.get("attr") or {}
    n_reg_ext = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_region_extract" and c.status == "ok"
    )
    pay, why = should_pay_f4_region_extract(
        mem,
        budget_left=ctx["t_end"] - time.time(),
        n_extract=n_reg_ext,
        region=attr.get("region"),
        x_dbu=attr.get("x_dbu"),
        y_dbu=attr.get("y_dbu"),
    )
    _set_admit(ctx, solver="direct")

    def _eval() -> bool:
        pick = ctx["mapped_pick"](
            [ctx["f1_wns_winner"](mem), ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            rtl=ctx["rtl"],
            liberty=ctx["liberty"],
            top=ctx["top"],
        )
        if not pick:
            return False
        mem.touch(pick)
        params = ctx["flowlab_params"]()
        util_e = float(params.get("coreUtilization") or 35.0)
        den_e = ctx["gpl_density"](util_e, params.get("placeDensityAddon") or 0.2)
        child = ctx["evaluate_f4_extract"](
            pick,
            mem,
            design_id=ctx["design_id"],
            variant=ctx["variant"],
            util=util_e,
            density=den_e,
            region=attr.get("region"),
            x_dbu=attr.get("x_dbu"),
            y_dbu=attr.get("y_dbu"),
            region_density=0.30,
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="f4_region_extract",
            parent=pick.id,
            region=attr.get("region"),
            region_bin=(child.artifacts or {}).get("region_bin"),
            n_r=(child.artifacts or {}).get("n_r"),
            droop_mv=child.qor.dynamic_ir_mv,
            gold=False,
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f4_region_extract", acquire_fidelity="F4_REGION_EXTRACT", pay=pay, why=why,
        evaluate=_eval, cost_key="F4_EXTRACT", fidelity="F4",
    )


def run_f4_pdn(ctx: dict) -> bool:
    from .acquire import should_pay_f4_pdn

    mem = ctx["mem"]
    variant = ctx["variant"]
    ext_hit, extract_id = _latest_extract(ctx)
    n_pdn_f4 = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_solver_a"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "finish") == extract_id
    )
    pay, why = should_pay_f4_pdn(
        mem,
        budget_left=ctx["t_end"] - time.time(),
        n_pdn=n_pdn_f4,
        variant=variant,
        extract_id=extract_id,
    )
    spec_pdn = ctx["next_pdn_spec"](mem, extract_id=extract_id) if pay else None
    _set_admit(ctx, solver="direct", extract_id=extract_id, extract_hit=ext_hit,
               spice=ext_hit["spice"] if ext_hit else None)

    def _eval() -> bool:
        if not spec_pdn:
            return False
        ingest = next(
            (c for c in mem.by_level("pdn") if (c.knobs or {}).get("source") == "ingest_pdn"),
            None,
        )
        child = ctx["evaluate_f4_pdn"](
            mem,
            spec_pdn,
            variant=variant,
            design_id=ctx["design_id"],
            parent_id=(ext_hit["candidate"].id if ext_hit else (ingest.id if ingest else None)),
            spice=ext_hit["spice"] if ext_hit else None,
            insts=ext_hit["insts"] if ext_hit else None,
            extract_id=extract_id,
            sta=ext_hit.get("sta") if ext_hit else None,
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="f4_solver_a",
            catalog=spec_pdn.get("name"),
            extract_id=extract_id,
            droop_mv=child.qor.dynamic_ir_mv,
            em_j=child.qor.em_j_a_m2,
            gold=False,
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="pdn", acquire_fidelity="F4_PDN", pay=pay, why=why, evaluate=_eval,
        cost_key="F4", fidelity="F4", require_plan=False,
    )


def _run_f4_solver_residual(
    ctx: dict,
    *,
    source: str,
    n_key: str,
    should_pay,
    level: str,
    acquire_fidelity: str,
    solver: str,
    via: str,
    spec_name: str,
    reason: str,
) -> bool:
    mem = ctx["mem"]
    variant = ctx["variant"]
    ext_hit, extract_id = _latest_extract(ctx)
    n_have = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == source
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "finish") == extract_id
    )
    pay, why = should_pay(
        mem,
        budget_left=ctx["t_end"] - time.time(),
        **{n_key: n_have},
        variant=variant,
        extract_id=extract_id,
    )
    _set_admit(ctx, solver=solver, extract_id=extract_id, extract_hit=ext_hit,
               spice=ext_hit["spice"] if ext_hit else None)

    def _eval() -> bool:
        ingest = next(
            (c for c in mem.by_level("pdn") if (c.knobs or {}).get("source") == "ingest_pdn"),
            None,
        )
        child = ctx["evaluate_f4_pdn"](
            mem,
            {"name": spec_name, **ctx["GOLD_KNOBS"]},
            variant=variant,
            design_id=ctx["design_id"],
            parent_id=(ext_hit["candidate"].id if ext_hit else (ingest.id if ingest else None)),
            spice=ext_hit["spice"] if ext_hit else None,
            insts=ext_hit["insts"] if ext_hit else None,
            extract_id=extract_id,
            solver=solver,
            sta=ext_hit.get("sta") if ext_hit else None,
        )
        if not child:
            return False
        extra = {}
        if solver == "krylov":
            extra["m"] = (child.artifacts or {}).get("m")
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via=via,
            extract_id=extract_id,
            droop_mv=child.qor.dynamic_ir_mv,
            em_j=child.qor.em_j_a_m2,
            gold=False,
            status=child.status,
            reason=reason,
            **extra,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level=level, acquire_fidelity=acquire_fidelity, pay=pay, why=why, evaluate=_eval,
        cost_key="F4", fidelity="F4",
    )


def run_f4_amg(ctx: dict) -> bool:
    from .acquire import should_pay_f4_amg

    return _run_f4_solver_residual(
        ctx,
        source="f4_solver_amg",
        n_key="n_amg",
        should_pay=should_pay_f4_amg,
        level="f4_amg",
        acquire_fidelity="F4_AMG",
        solver="amg",
        via="f4_solver_amg",
        spec_name="amg_residual",
        reason="mf-amg-residual-vs-direct",
    )


def run_f4_ras(ctx: dict) -> bool:
    from .acquire import should_pay_f4_ras

    return _run_f4_solver_residual(
        ctx,
        source="f4_solver_ras",
        n_key="n_ras",
        should_pay=should_pay_f4_ras,
        level="f4_ras",
        acquire_fidelity="F4_RAS",
        solver="ras",
        via="f4_solver_ras",
        spec_name="ras_residual",
        reason="mf-ras-residual-vs-direct",
    )


def run_f4_krylov(ctx: dict) -> bool:
    from .acquire import should_pay_f4_krylov

    return _run_f4_solver_residual(
        ctx,
        source="f4_solver_krylov",
        n_key="n_krylov",
        should_pay=should_pay_f4_krylov,
        level="f4_krylov",
        acquire_fidelity="F4_KRYLOV",
        solver="krylov",
        via="f4_solver_krylov",
        spec_name="krylov_residual",
        reason="mf-krylov-mor-residual-vs-direct",
    )


def run_f4_activity(ctx: dict) -> bool:
    from .acquire import should_pay_host_arrivals

    mem = ctx["mem"]
    n_arr = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_host_arrivals" and c.status == "ok"
    )
    pay, why = should_pay_host_arrivals(
        mem, budget_left=ctx["t_end"] - time.time(), n_arr=n_arr
    )

    def _eval() -> bool:
        host_arr = ctx["iscale_host"](mem)
        if not host_arr:
            return False
        child = ctx["evaluate_host_arrivals"](host_arr, mem, design_id=ctx["design_id"])
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F3",
            via="f4_host_arrivals",
            parent=host_arr.id,
            host_source=(host_arr.knobs or {}).get("source") or host_arr.level,
            n_inst=(child.artifacts or {}).get("n_inst"),
            status=child.status,
            reason=why,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f4_activity", acquire_fidelity="F3_HOST_ARRIVALS", pay=pay, why=why,
        evaluate=_eval, cost_key="F3", fidelity="F3",
    )


def run_f4_host_extract(ctx: dict) -> bool:
    from .acquire import should_pay_f4_host_extract

    mem = ctx["mem"]
    n_host_ext = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_host_extract" and c.status == "ok"
    )
    pay, why = should_pay_f4_host_extract(
        mem, budget_left=ctx["t_end"] - time.time(), n_extract=n_host_ext
    )
    _set_admit(ctx, solver="direct")

    def _eval() -> bool:
        host_ex = ctx["iscale_host"](mem)
        if not host_ex or not (host_ex.artifacts or {}).get("mapped_v"):
            return False
        params = ctx["flowlab_params"]()
        util_h = float(params.get("coreUtilization") or 35.0)
        den_h = ctx["gpl_density"](util_h, params.get("placeDensityAddon") or 0.2)
        arr_hit = ctx["latest_host_arrivals"](mem)
        child = ctx["evaluate_f4_extract"](
            host_ex,
            mem,
            design_id=ctx["design_id"],
            variant=ctx["variant"],
            util=util_h,
            density=den_h,
            kind="host",
            sta=arr_hit["sta"] if arr_hit else None,
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="f4_host_extract",
            parent=host_ex.id,
            host_source=(host_ex.knobs or {}).get("source") or host_ex.level,
            n_r=(child.artifacts or {}).get("n_r"),
            n_sta=(child.artifacts or {}).get("n_sta_inst"),
            droop_mv=child.qor.dynamic_ir_mv,
            gold=False,
            status=child.status,
            reason=why,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f4_host_extract", acquire_fidelity="F4_HOST_EXTRACT", pay=pay, why=why,
        evaluate=_eval, cost_key="F4_EXTRACT", fidelity="F4",
    )


def run_f4_host_region(ctx: dict) -> bool:
    from .acquire import should_pay_f4_host_region

    mem = ctx["mem"]
    n_hre = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_host_region_extract" and c.status == "ok"
    )
    pay, why = should_pay_f4_host_region(
        mem, budget_left=ctx["t_end"] - time.time(), n_extract=n_hre
    )
    _set_admit(ctx, solver="direct")

    def _eval() -> bool:
        host_rg = ctx["iscale_host"](mem)
        host_ext_c = ctx["latest_host_extract_cand"](mem)
        hattr = (host_ext_c.attr or {}) if host_ext_c else {}
        if not host_rg or not (host_rg.artifacts or {}).get("mapped_v"):
            return False
        if not (hattr.get("region") or hattr.get("x_dbu") is not None):
            return False
        params = ctx["flowlab_params"]()
        util_hr = float(params.get("coreUtilization") or 35.0)
        den_hr = ctx["gpl_density"](util_hr, params.get("placeDensityAddon") or 0.2)
        arr_hr = ctx["latest_host_arrivals"](mem)
        child = ctx["evaluate_f4_extract"](
            host_rg,
            mem,
            design_id=ctx["design_id"],
            variant=ctx["variant"],
            util=util_hr,
            density=den_hr,
            kind="host_region",
            region=hattr.get("region"),
            x_dbu=hattr.get("x_dbu"),
            y_dbu=hattr.get("y_dbu"),
            region_density=0.30,
            sta=arr_hr["sta"] if arr_hr else None,
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="f4_host_region_extract",
            parent=host_rg.id,
            host_source=(host_rg.knobs or {}).get("source") or host_rg.level,
            region=hattr.get("region"),
            region_bin=(child.artifacts or {}).get("region_bin"),
            n_r=(child.artifacts or {}).get("n_r"),
            droop_mv=child.qor.dynamic_ir_mv,
            gold=False,
            status=child.status,
            reason=why,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f4_host_region", acquire_fidelity="F4_HOST_REGION", pay=pay, why=why,
        evaluate=_eval, cost_key="F4_EXTRACT", fidelity="F4",
    )


def run_f4_scale(ctx: dict) -> bool:
    from .acquire import should_pay_f4_scale

    mem = ctx["mem"]
    variant = ctx["variant"]
    n_scale = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_iscale" and c.status == "ok"
    )
    pay, why = should_pay_f4_scale(
        mem, budget_left=ctx["t_end"] - time.time(), n_scale=n_scale, variant=variant
    )
    ext_hit, extract_id = _latest_extract(ctx)
    host_hit = ctx["latest_ok_host_extract"](mem)
    mesh = host_hit or ext_hit
    _set_admit(
        ctx,
        solver="direct",
        extract_id=str(mesh["extract_id"]) if mesh else extract_id,
        extract_hit=mesh,
        spice=mesh["spice"] if mesh else None,
    )

    def _eval() -> bool:
        base_p = None
        for c in mem.by_level("logic"):
            if c.status == "ok" and c.knobs.get("name") == "liberty_default":
                _w, p = ctx["timing_of"](mem, c)
                if p:
                    base_p = p
                    break
        pick = ctx["iscale_host"](mem)
        if not pick or not base_p:
            return False
        use_ext = bool(mesh)
        arr_hit = ctx["latest_host_arrivals"](mem)
        sta = arr_hit["sta"] if arr_hit else (mesh.get("sta") if mesh else None)
        sta_via = (
            "f4_host_arrivals"
            if arr_hit
            else ("f4_host_extract" if host_hit else ("extract" if ext_hit else None))
        )
        child = ctx["evaluate_f4_scale"](
            pick,
            mem,
            variant=variant,
            design_id=ctx["design_id"],
            baseline_power_w=base_p,
            spice=mesh["spice"] if use_ext else None,
            insts=mesh["insts"] if use_ext else None,
            extract_id=str(mesh["extract_id"]) if use_ext else "finish",
            sta=sta,
            sta_via=sta_via,
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="f4_iscale",
            parent=pick.id,
            host_level=pick.level,
            host_source=(pick.knobs or {}).get("source") or pick.level,
            i_scale=(child.knobs or {}).get("i_scale"),
            extract_id=(child.knobs or {}).get("extract_id"),
            sta_via=(child.knobs or {}).get("sta_via"),
            droop_mv=child.qor.dynamic_ir_mv,
            em_j=child.qor.em_j_a_m2,
            gold=False,
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f4_scale", acquire_fidelity="F4_ISCALE", pay=pay, why=why, evaluate=_eval,
        cost_key="F4", fidelity="F4", require_plan=False,
    )


def run_residual_steer(ctx: dict) -> bool:
    from .acquire import should_pay_residual_steer
    from .active import steer_from_residual
    from .fidelity import evaluate_cell_size, evaluate_f5_local, evaluate_net_buffer

    mem = ctx["mem"]
    steer = steer_from_residual(mem)
    n_steer = sum(1 for c in mem.all() if (c.attr or {}).get("via") == "active_residual" and c.status == "ok")
    pay, why = should_pay_residual_steer(
        mem, budget_left=ctx["t_end"] - time.time(), steer=steer, n_steer=n_steer
    )

    def _eval() -> bool:
        host = mem.get(str(steer.get("host_id") or "")) if steer and steer.get("host_id") else None
        child = None
        if not steer or host is None:
            return False
        if steer["level"] == "f5_local":
            mem.touch(host)
            child = evaluate_f5_local(host, mem, design_id=ctx["design_id"])
        elif steer["level"] == "cell":
            mem.touch(host)
            child = evaluate_cell_size(host, mem, design_id=ctx["design_id"], cells=list(steer.get("cells") or []))
        elif steer["level"] == "net":
            mem.touch(host)
            child = evaluate_net_buffer(host, mem, design_id=ctx["design_id"], hops=list(steer.get("hops") or []))
        if not child:
            return False
        child.attr = dict(child.attr or {})
        child.attr["via"] = "active_residual"
        child.attr["steer"] = {k: steer[k] for k in steer if k != "cells" and k != "hops"}
        mem.touch(child)
        ctx["step"](
            "evaluate",
            id=child.id,
            level=child.level,
            fidelity=child.fidelity,
            via="active_residual",
            parent=host.id,
            host_level=steer.get("host_level") or host.level,
            residual_ns=steer.get("residual_ns"),
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            status=child.status,
            reason=steer.get("reason"),
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="residual_steer", acquire_fidelity="RESIDUAL_STEER", pay=pay, why=why,
        evaluate=_eval, acquire_extra={"steer": steer},
    )


def run_port_steer(ctx: dict) -> bool:
    from .acquire import should_pay_port_steer
    from .active import steer_from_port_residual
    from .fidelity import evaluate_net_buffer

    mem = ctx["mem"]
    steer_port = steer_from_port_residual(mem)
    n_psteer = sum(
        1 for c in mem.all() if (c.attr or {}).get("via") == "active_f5_port" and c.status == "ok"
    )
    pay, why = should_pay_port_steer(
        mem, budget_left=ctx["t_end"] - time.time(), steer=steer_port, n_steer=n_psteer
    )

    def _eval() -> bool:
        host = mem.get(str(steer_port.get("host_id") or "")) if steer_port and steer_port.get("host_id") else None
        if host is None or not steer_port or steer_port.get("level") != "net":
            return False
        mem.touch(host)
        child = evaluate_net_buffer(
            host,
            mem,
            design_id=ctx["design_id"],
            hops=list(steer_port.get("hops") or []),
            source="net_buffer_spef",
        )
        if not child:
            return False
        child.attr = dict(child.attr or {})
        child.attr["via"] = "active_f5_port"
        child.attr["steer"] = {k: steer_port[k] for k in steer_port if k != "hops"}
        mem.touch(child)
        ctx["step"](
            "evaluate",
            id=child.id,
            level="net",
            fidelity="F3",
            via="active_f5_port",
            parent=host.id,
            n_changed=(child.artifacts or {}).get("n_changed"),
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            status=child.status,
            reason=steer_port.get("reason"),
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="port_steer", acquire_fidelity="PORT_STEER", pay=pay, why=why,
        evaluate=_eval, acquire_extra={"steer": steer_port},
    )


def run_f2_region(ctx: dict) -> bool:
    from .acquire import should_pay_f2_region
    from .fidelity import evaluate_f2_gpl
    from .physical_space import gpl_density

    mem = ctx["mem"]
    attr = ctx["attr"]
    n_reg = sum(
        1
        for c in mem.by_level("physical")
        if (c.knobs or {}).get("source") == "f2_openroad_gpl_region" and c.status == "ok"
    )
    pay, why = should_pay_f2_region(
        mem,
        budget_left=ctx["t_end"] - time.time(),
        n_region=n_reg,
        region=attr.get("region"),
        x_dbu=attr.get("x_dbu"),
        y_dbu=attr.get("y_dbu"),
    )

    def _eval() -> bool:
        pick = ctx["mapped_pick"](
            [ctx["f1_wns_winner"](mem), ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            rtl=ctx["rtl"],
            liberty=ctx["liberty"],
            top=ctx["top"],
        )
        if not pick:
            return False
        mem.touch(pick)
        params = ctx["flowlab_params"]()
        util_r = float(params.get("coreUtilization") or 35.0)
        den_r = gpl_density(util_r, params.get("placeDensityAddon") or 0.2)
        child = evaluate_f2_gpl(
            pick,
            mem,
            design_id=ctx["design_id"],
            util=util_r,
            density=den_r,
            extra_knobs={
                "region": attr.get("region"),
                "x_dbu": attr.get("x_dbu"),
                "y_dbu": attr.get("y_dbu"),
                "region_density": 0.30,
            },
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="physical",
            fidelity="F2",
            via="f2_openroad_gpl_region",
            parent=pick.id,
            region=attr.get("region"),
            hpwl_um=(child.artifacts or {}).get("hpwl_um"),
            region_bin=(child.artifacts or {}).get("region_bin"),
            overflow=child.qor.congestion,
            status=child.status,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f2_region", acquire_fidelity="F2_REGION", pay=pay, why=why, evaluate=_eval,
    )


def run_ir_steer(ctx: dict) -> bool:
    from .acquire import extract_on_disk, should_pay_ir_steer
    from .active import steer_from_ir_residual

    mem = ctx["mem"]
    step = ctx["step"]
    t_end = ctx["t_end"]
    planned_ir = planned(ctx["plan"], "ir_steer")
    paid = False
    while planned_ir and time.time() < t_end:
        steer_ir = steer_from_ir_residual(mem)
        n_ir_st = sum(
            1 for c in mem.all() if (c.attr or {}).get("via") == "active_f4_ir" and c.status == "ok"
        )
        pay_ir, why_ir = should_pay_ir_steer(
            mem, budget_left=t_end - time.time(), steer=steer_ir, n_steer=n_ir_st
        )
        step("acquire", fidelity="IR_STEER", pay=pay_ir, why=why_ir, steer=steer_ir)
        if not pay_ir or not steer_ir:
            break
        spec = steer_ir.get("spec") or {}
        eid = str(steer_ir.get("extract_id") or "")
        hit = extract_on_disk(mem, eid) if eid else None
        if not spec or not hit:
            break
        child = ctx["evaluate_f4_pdn"](
            mem,
            spec,
            variant=ctx["variant"],
            design_id=ctx["design_id"],
            parent_id=hit["candidate"].id,
            spice=hit["spice"],
            insts=hit["insts"],
            extract_id=eid,
            sta=hit.get("sta"),
        )
        if not child:
            break
        child.attr = dict(child.attr or {})
        child.attr["via"] = "active_f4_ir"
        child.attr["steer"] = {k: steer_ir[k] for k in steer_ir if k != "spec"}
        mem.touch(child)
        step(
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="active_f4_ir",
            parent=hit["candidate"].id,
            catalog=spec.get("name"),
            extract_id=eid,
            droop_mv=child.qor.dynamic_ir_mv,
            gold=False,
            status=child.status,
            reason=steer_ir.get("reason"),
        )
        paid = True
    return paid


def run_host_ir_steer(ctx: dict) -> bool:
    from .acquire import extract_on_disk, should_pay_host_ir_steer
    from .active import steer_from_host_ir_residual

    mem = ctx["mem"]
    step = ctx["step"]
    t_end = ctx["t_end"]
    planned_hir = planned(ctx["plan"], "host_ir_steer")
    paid = False
    while planned_hir and time.time() < t_end:
        steer_hir = steer_from_host_ir_residual(mem)
        n_hir_st = sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_host_ir" and c.status == "ok"
        )
        pay_hir, why_hir = should_pay_host_ir_steer(
            mem, budget_left=t_end - time.time(), steer=steer_hir, n_steer=n_hir_st
        )
        step("acquire", fidelity="HOST_IR_STEER", pay=pay_hir, why=why_hir, steer=steer_hir)
        if not pay_hir or not steer_hir:
            break
        spec = steer_hir.get("spec") or {}
        eid = str(steer_hir.get("extract_id") or "")
        hit = extract_on_disk(mem, eid) if eid else None
        if not spec or not hit:
            break
        child = ctx["evaluate_f4_pdn"](
            mem,
            spec,
            variant=ctx["variant"],
            design_id=ctx["design_id"],
            parent_id=hit["candidate"].id,
            spice=hit["spice"],
            insts=hit["insts"],
            extract_id=eid,
            sta=hit.get("sta"),
        )
        if not child:
            break
        child.attr = dict(child.attr or {})
        child.attr["via"] = "active_f4_host_ir"
        child.attr["steer"] = {k: steer_hir[k] for k in steer_hir if k != "spec"}
        mem.touch(child)
        step(
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="active_f4_host_ir",
            parent=hit["candidate"].id,
            catalog=spec.get("name"),
            extract_id=eid,
            host_source=steer_hir.get("host_source"),
            droop_mv=child.qor.dynamic_ir_mv,
            gold=False,
            status=child.status,
            reason=steer_hir.get("reason"),
        )
        paid = True
    return paid


def run_f4_scale_win(ctx: dict) -> bool:
    from .acquire import extract_on_disk, should_pay_f4_scale_win
    from .active import iscale_parent, winning_host_pdn

    mem = ctx["mem"]
    n_sw = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_iscale_win" and c.status == "ok"
    )
    pay, why = should_pay_f4_scale_win(
        mem, budget_left=ctx["t_end"] - time.time(), n_scale=n_sw, variant=ctx["variant"]
    )

    def _eval() -> bool:
        base_p_w = None
        for c in mem.by_level("logic"):
            if c.status == "ok" and c.knobs.get("name") == "liberty_default":
                _w, p = ctx["timing_of"](mem, c)
                if p:
                    base_p_w = p
                    break
        pick_w = iscale_parent(mem)
        win = winning_host_pdn(mem)
        eid_w = str((win.knobs or {}).get("extract_id") or win.id) if win else ""
        hit_w = extract_on_disk(mem, eid_w) if eid_w else None
        if not (pick_w and base_p_w and win and hit_w):
            return False
        arr_w = ctx["latest_host_arrivals"](mem)
        child = ctx["evaluate_f4_scale"](
            pick_w,
            mem,
            variant=ctx["variant"],
            design_id=ctx["design_id"],
            baseline_power_w=base_p_w,
            pkg_r=float((win.knobs or {}).get("pkg_r") or 0.05),
            pkg_l=float((win.knobs or {}).get("pkg_l") or 2e-10),
            c_decap=float((win.knobs or {}).get("c_decap") or 50e-15),
            spice=hit_w["spice"],
            insts=hit_w["insts"],
            extract_id=eid_w,
            sta=arr_w["sta"] if arr_w else hit_w.get("sta"),
            sta_via="f4_host_arrivals" if arr_w else "f4_iscale_win",
            source="f4_iscale_win",
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="f4_iscale_win",
            parent=pick_w.id,
            host_level=pick_w.level,
            host_source=(pick_w.knobs or {}).get("source") or pick_w.level,
            win_source=(win.knobs or {}).get("name") or (win.attr or {}).get("via"),
            i_scale=(child.knobs or {}).get("i_scale"),
            extract_id=eid_w,
            c_decap=(child.knobs or {}).get("c_decap"),
            droop_mv=child.qor.dynamic_ir_mv,
            gold=False,
            status=child.status,
            reason=why,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="f4_scale_win", acquire_fidelity="F4_ISCALE_WIN", pay=pay, why=why, evaluate=_eval,
    )


def run_ir_cell(ctx: dict) -> bool:
    from .acquire import should_pay_ir_cell
    from .active import ir_hotspot_cells, iscale_parent
    from .fidelity import evaluate_cell_size

    mem = ctx["mem"]
    n_irc = sum(
        1
        for c in mem.by_level("cell")
        if (c.knobs or {}).get("source") == "cell_size_ir" and c.status == "ok"
    )
    pay, why = should_pay_ir_cell(mem, budget_left=ctx["t_end"] - time.time(), n_cell=n_irc)

    def _eval() -> bool:
        host_ic = iscale_parent(mem)
        spec_ic = ir_hotspot_cells(mem)
        if not (host_ic and spec_ic and spec_ic.get("cells")):
            return False
        if not (host_ic.artifacts or {}).get("mapped_v"):
            host_ic = ctx["ensure_mapped_netlist"](
                host_ic, rtl=ctx["rtl"], liberty=ctx["liberty"], top=ctx["top"]
            )
            mem.touch(host_ic)
        child = evaluate_cell_size(
            host_ic,
            mem,
            design_id=ctx["design_id"],
            cells=list(spec_ic["cells"]),
            source="cell_size_ir",
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="cell",
            fidelity="F3",
            via="active_f4_ir_cell",
            parent=host_ic.id,
            modules=spec_ic.get("modules"),
            region=spec_ic.get("region"),
            n_changed=(child.artifacts or {}).get("n_changed"),
            wns_ns=(child.artifacts or {}).get("wns_ns"),
            area_um2=child.qor.area_um2,
            gold=False,
            status=child.status,
            reason=why,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="ir_cell", acquire_fidelity="IR_CELL", pay=pay, why=why, evaluate=_eval,
    )


def run_ir_cell_extract(ctx: dict) -> bool:
    from .acquire import should_pay_ir_cell_extract
    from .active import ir_cell_host

    mem = ctx["mem"]
    n_irce = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_ir_cell_extract" and c.status == "ok"
    )
    pay, why = should_pay_ir_cell_extract(
        mem, budget_left=ctx["t_end"] - time.time(), n_extract=n_irce
    )

    def _eval() -> bool:
        host_ice = ir_cell_host(mem)
        if not (host_ice and (host_ice.artifacts or {}).get("mapped_v")):
            return False
        params = ctx["flowlab_params"]()
        util_ice = float(params.get("coreUtilization") or 35.0)
        den_ice = ctx["gpl_density"](util_ice, params.get("placeDensityAddon") or 0.2)
        child = ctx["evaluate_f4_extract"](
            host_ice,
            mem,
            design_id=ctx["design_id"],
            variant=ctx["variant"],
            util=util_ice,
            density=den_ice,
            kind="ir_cell",
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="f4_ir_cell_extract",
            parent=host_ice.id,
            host_source=(host_ice.knobs or {}).get("source") or host_ice.level,
            n_r=(child.artifacts or {}).get("n_r"),
            n_sta=(child.artifacts or {}).get("n_sta_inst"),
            droop_mv=child.qor.dynamic_ir_mv,
            residual_mv=(child.attr or {}).get("residual_mv"),
            gold=False,
            status=child.status,
            reason=why,
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="ir_cell_extract", acquire_fidelity="F4_IR_CELL_EXTRACT", pay=pay, why=why,
        evaluate=_eval,
    )


def run_ir_cell_pdn(ctx: dict) -> bool:
    from .acquire import extract_on_disk, should_pay_ir_cell_pdn
    from .active import steer_from_ir_cell_residual

    mem = ctx["mem"]
    n_icp = sum(
        1
        for c in mem.all()
        if (c.attr or {}).get("via") == "active_f4_ir_cell_pdn" and c.status == "ok"
    )
    steer_icp = steer_from_ir_cell_residual(mem)
    pay, why = should_pay_ir_cell_pdn(
        mem, budget_left=ctx["t_end"] - time.time(), steer=steer_icp, n_steer=n_icp
    )

    def _eval() -> bool:
        spec_icp = (steer_icp or {}).get("spec") or {}
        eid_icp = str((steer_icp or {}).get("extract_id") or "")
        hit_icp = extract_on_disk(mem, eid_icp) if eid_icp else None
        if not spec_icp or not hit_icp:
            return False
        child = ctx["evaluate_f4_pdn"](
            mem,
            spec_icp,
            variant=ctx["variant"],
            design_id=ctx["design_id"],
            parent_id=hit_icp["candidate"].id,
            spice=hit_icp["spice"],
            insts=hit_icp["insts"],
            extract_id=eid_icp,
            sta=hit_icp.get("sta"),
        )
        if not child:
            return False
        child.attr = dict(child.attr or {})
        child.attr["via"] = "active_f4_ir_cell_pdn"
        child.attr["steer"] = {k: steer_icp[k] for k in steer_icp if k != "spec"}
        mem.touch(child)
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="active_f4_ir_cell_pdn",
            parent=hit_icp["candidate"].id,
            catalog=spec_icp.get("name"),
            extract_id=eid_icp,
            droop_mv=child.qor.dynamic_ir_mv,
            gold=False,
            status=child.status,
            reason=steer_icp.get("reason"),
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="ir_cell_pdn", acquire_fidelity="IR_CELL_PDN", pay=pay, why=why,
        evaluate=_eval, acquire_extra={"steer": steer_icp},
    )


def run_ir_cell_region(ctx: dict) -> bool:
    from .acquire import should_pay_ir_cell_region
    from .active import ir_cell_host, steer_from_ir_cell_hotspot

    mem = ctx["mem"]
    n_icr = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_ir_cell_region_extract" and c.status == "ok"
    )
    steer_icr = steer_from_ir_cell_hotspot(mem)
    pay, why = should_pay_ir_cell_region(
        mem, budget_left=ctx["t_end"] - time.time(), steer=steer_icr, n_extract=n_icr
    )

    def _eval() -> bool:
        host_icr = ir_cell_host(mem)
        if not (host_icr and (host_icr.artifacts or {}).get("mapped_v") and steer_icr):
            return False
        params = ctx["flowlab_params"]()
        util_icr = float(params.get("coreUtilization") or 35.0)
        den_icr = ctx["gpl_density"](util_icr, params.get("placeDensityAddon") or 0.2)
        child = ctx["evaluate_f4_extract"](
            host_icr,
            mem,
            design_id=ctx["design_id"],
            variant=ctx["variant"],
            util=util_icr,
            density=den_icr,
            kind="ir_cell_region",
            region=steer_icr.get("region"),
            x_dbu=steer_icr.get("x_dbu"),
            y_dbu=steer_icr.get("y_dbu"),
            region_density=0.30,
        )
        if not child:
            return False
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="f4_ir_cell_region_extract",
            parent=host_icr.id,
            region=steer_icr.get("region"),
            n_r=(child.artifacts or {}).get("n_r"),
            droop_mv=child.qor.dynamic_ir_mv,
            residual_mv=(child.attr or {}).get("residual_mv"),
            gold=False,
            status=child.status,
            reason=steer_icr.get("reason"),
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="ir_cell_region", acquire_fidelity="F4_IR_CELL_REGION", pay=pay, why=why,
        evaluate=_eval, acquire_extra={"steer": steer_icr},
    )


def run_ir_cell_region_pdn(ctx: dict) -> bool:
    from .acquire import extract_on_disk, should_pay_ir_cell_region_pdn
    from .active import steer_from_ir_cell_region_residual, winning_host_pdn

    mem = ctx["mem"]
    n_icrp = sum(
        1
        for c in mem.all()
        if (c.attr or {}).get("via") == "active_f4_ir_cell_region_pdn" and c.status == "ok"
    )
    steer_icrp = steer_from_ir_cell_region_residual(mem)
    pay, why = should_pay_ir_cell_region_pdn(
        mem, budget_left=ctx["t_end"] - time.time(), steer=steer_icrp, n_steer=n_icrp
    )

    def _eval() -> bool:
        spec_icrp = (steer_icrp or {}).get("spec") or {}
        eid_icrp = str((steer_icrp or {}).get("extract_id") or "")
        hit_icrp = extract_on_disk(mem, eid_icrp) if eid_icrp else None
        if not spec_icrp or not hit_icrp:
            return False
        child = ctx["evaluate_f4_pdn"](
            mem,
            spec_icrp,
            variant=ctx["variant"],
            design_id=ctx["design_id"],
            parent_id=hit_icrp["candidate"].id,
            spice=hit_icrp["spice"],
            insts=hit_icrp["insts"],
            extract_id=eid_icrp,
            sta=hit_icrp.get("sta"),
        )
        if not child:
            return False
        child.attr = dict(child.attr or {})
        child.attr["via"] = "active_f4_ir_cell_region_pdn"
        child.attr["steer"] = {k: steer_icrp[k] for k in steer_icrp if k != "spec"}
        champ = winning_host_pdn(mem)
        if champ and champ.qor.dynamic_ir_mv is not None and child.qor.dynamic_ir_mv is not None:
            child.attr["residual_vs_host_win_mv"] = float(child.qor.dynamic_ir_mv) - float(
                champ.qor.dynamic_ir_mv
            )
            child.attr["residual_vs_host_win"] = champ.id
        mem.touch(child)
        ctx["step"](
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via="active_f4_ir_cell_region_pdn",
            parent=hit_icrp["candidate"].id,
            catalog=spec_icrp.get("name"),
            extract_id=eid_icrp,
            droop_mv=child.qor.dynamic_ir_mv,
            residual_vs_host_win_mv=(child.attr or {}).get("residual_vs_host_win_mv"),
            gold=False,
            status=child.status,
            reason=steer_icrp.get("reason"),
        )
        return True

    return _pay_and_maybe_eval(
        ctx, level="ir_cell_region_pdn", acquire_fidelity="IR_CELL_REGION_PDN", pay=pay, why=why,
        evaluate=_eval, acquire_extra={"steer": steer_icrp},
    )


STAGE_F2_FAST = Stage(level="f2_fast", run=run_f2_fast, cost_key="F2_FAST", max_shots=4)
STAGE_F2_GPL = Stage(level="f2_gpl", run=run_f2_gpl, acquire_fidelity="F2_GPL", cost_key="F2_GPL", max_shots=1, min_s=8.0)
STAGE_F3_STA = Stage(level="f3_sta", run=run_f3_sta, acquire_fidelity="F3", cost_key="F3", max_shots=8, min_s=1.0)
STAGE_F3_SDF = Stage(level="f3_sdf", run=run_f3_sdf, acquire_fidelity="F3_SDF", cost_key="F3_SDF", max_shots=1, min_s=1.0)
STAGE_ROUTING = Stage(level="routing", run=run_routing, acquire_fidelity="F2_GRT", cost_key="F2_GRT", max_shots=1, min_s=8.0)
STAGE_F5_DRT = Stage(level="f5_drt", run=run_f5_drt, acquire_fidelity="F5", cost_key="F5", max_shots=1, min_s=12.0)
STAGE_F3_SPEF = Stage(level="f3_spef", run=run_f3_spef, acquire_fidelity="F3_SPEF", cost_key="F3", max_shots=1, min_s=1.0)
STAGE_F5_CTS = Stage(level="f5_cts", run=run_f5_cts, acquire_fidelity="F5_CTS", cost_key="F5_CTS", max_shots=1, min_s=25.0)
STAGE_F5_LOCAL = Stage(level="f5_local", run=run_f5_local, acquire_fidelity="F5_LOCAL", cost_key="F5", max_shots=1, min_s=12.0)
STAGE_F5_PORT = Stage(level="f5_port", run=run_f5_port, acquire_fidelity="F5_PORT", cost_key="F5", max_shots=1, min_s=12.0)
STAGE_SYNTHESIS = Stage(level="synthesis", run=run_synthesis, acquire_fidelity="F1_SYNTH", cost_key="F1", max_shots=1, min_s=8.0)
STAGE_CELL = Stage(level="cell", run=run_cell, acquire_fidelity="CELL_SIZE", cost_key="F3", max_shots=1, min_s=3.0)
STAGE_NET = Stage(level="net", run=run_net, acquire_fidelity="NET_BUF", cost_key="F3", max_shots=1, min_s=3.0)
STAGE_NET_PORT = Stage(level="net_port", run=run_net_port, acquire_fidelity="NET_PORT", cost_key="F3", max_shots=1, min_s=3.0)
STAGE_PHYSICAL_CATALOG = Stage(
    level="physical_catalog", run=run_physical_catalog, acquire_fidelity="F2_GPL_CATALOG",
    cost_key="F2_GPL", max_shots=1, min_s=8.0,
)
STAGE_RESIDUAL_STEER = Stage(level="residual_steer", run=run_residual_steer, acquire_fidelity="RESIDUAL_STEER")
STAGE_PORT_STEER = Stage(level="port_steer", run=run_port_steer, acquire_fidelity="PORT_STEER")
STAGE_F2_REGION = Stage(level="f2_region", run=run_f2_region, acquire_fidelity="F2_REGION")
STAGE_F4_EXTRACT = Stage(level="f4_extract", run=run_f4_extract, acquire_fidelity="F4_EXTRACT", cost_key="F4_EXTRACT", needs_admit=True)
STAGE_F4_REGION_EXTRACT = Stage(level="f4_region_extract", run=run_f4_region_extract, acquire_fidelity="F4_REGION_EXTRACT", cost_key="F4_EXTRACT", needs_admit=True)
STAGE_F4_PDN = Stage(level="pdn", run=run_f4_pdn, acquire_fidelity="F4_PDN", cost_key="F4", needs_admit=True)
STAGE_F4_AMG = Stage(level="f4_amg", run=run_f4_amg, acquire_fidelity="F4_AMG", cost_key="F4", needs_admit=True)
STAGE_F4_RAS = Stage(level="f4_ras", run=run_f4_ras, acquire_fidelity="F4_RAS", cost_key="F4", needs_admit=True)
STAGE_F4_KRYLOV = Stage(level="f4_krylov", run=run_f4_krylov, acquire_fidelity="F4_KRYLOV", cost_key="F4", needs_admit=True)
STAGE_F4_ACTIVITY = Stage(level="f4_activity", run=run_f4_activity, acquire_fidelity="F3_HOST_ARRIVALS", cost_key="F3")
STAGE_F4_HOST_EXTRACT = Stage(level="f4_host_extract", run=run_f4_host_extract, acquire_fidelity="F4_HOST_EXTRACT", cost_key="F4_EXTRACT", needs_admit=True)
STAGE_F4_HOST_REGION = Stage(level="f4_host_region", run=run_f4_host_region, acquire_fidelity="F4_HOST_REGION", cost_key="F4_EXTRACT", needs_admit=True)
STAGE_F4_SCALE = Stage(level="f4_scale", run=run_f4_scale, acquire_fidelity="F4_ISCALE", cost_key="F4", needs_admit=True)
STAGE_IR_STEER = Stage(level="ir_steer", run=run_ir_steer, acquire_fidelity="IR_STEER")
STAGE_HOST_IR_STEER = Stage(level="host_ir_steer", run=run_host_ir_steer, acquire_fidelity="HOST_IR_STEER")
STAGE_F4_SCALE_WIN = Stage(level="f4_scale_win", run=run_f4_scale_win, acquire_fidelity="F4_ISCALE_WIN")
STAGE_IR_CELL = Stage(level="ir_cell", run=run_ir_cell, acquire_fidelity="IR_CELL")
STAGE_IR_CELL_EXTRACT = Stage(level="ir_cell_extract", run=run_ir_cell_extract, acquire_fidelity="F4_IR_CELL_EXTRACT")
STAGE_IR_CELL_PDN = Stage(level="ir_cell_pdn", run=run_ir_cell_pdn, acquire_fidelity="IR_CELL_PDN")
STAGE_IR_CELL_REGION = Stage(level="ir_cell_region", run=run_ir_cell_region, acquire_fidelity="F4_IR_CELL_REGION")
STAGE_IR_CELL_REGION_PDN = Stage(level="ir_cell_region_pdn", run=run_ir_cell_region_pdn, acquire_fidelity="IR_CELL_REGION_PDN")
STAGE_IR_CHAMP_FAMILY = Stage(level="ir_champ_family", run=run_ir_champ_family)
STAGE_IR_INSPECT = Stage(level="ir_inspect", run=run_ir_inspect_loops)
STAGE_WINNING_IR_REGION_CELL = Stage(level="winning_ir_region_cell_family", run=run_winning_ir_region_cell)
STAGE_IR_SOLVERS = Stage(level="ir_solvers", run=run_ir_solvers)

# Consecutive declarative slices. GRT order is data: STA → ROUTING → SDF.
# residual/port/f2_region live in STAGES_STEER_GAP (C1). C7 solvers sit after refine.
STAGES_LOGIC_TRANSFORM = (STAGE_SYNTHESIS, STAGE_CELL, STAGE_NET, STAGE_NET_PORT)
STAGES_PLACE_ROUTE = (
    STAGE_F2_FAST, STAGE_F2_GPL, STAGE_F3_STA, STAGE_ROUTING, STAGE_F3_SDF,
    STAGE_F5_DRT, STAGE_F3_SPEF, STAGE_F5_CTS, STAGE_F5_LOCAL,
)
STAGES_F4_HEAD = (
    STAGE_F4_EXTRACT, STAGE_F4_REGION_EXTRACT, STAGE_F4_PDN,
    STAGE_F4_AMG, STAGE_F4_RAS, STAGE_F4_KRYLOV, STAGE_F4_ACTIVITY,
    STAGE_F4_HOST_EXTRACT, STAGE_F4_HOST_REGION, STAGE_F4_SCALE,
)
# residual / port / f2_region sit BETWEEN place-route and F4 head.
# F5_PORT and PHYSICAL_CATALOG stay in this gap so runtime order is unchanged.
STAGES_STEER_GAP = (
    STAGE_RESIDUAL_STEER, STAGE_F5_PORT, STAGE_PORT_STEER,
    STAGE_PHYSICAL_CATALOG, STAGE_F2_REGION,
)
STAGES_IR_STEER = (STAGE_IR_STEER, STAGE_HOST_IR_STEER, STAGE_F4_SCALE_WIN)
STAGES_IR_CELL = (
    STAGE_IR_CELL, STAGE_IR_CELL_EXTRACT, STAGE_IR_CELL_PDN,
    STAGE_IR_CELL_REGION, STAGE_IR_CELL_REGION_PDN,
)
# winning_ir catalog + I-scale champ + ir_cell_champ/cone. Inner planned/why stay.
STAGES_IR_CHAMP = (STAGE_IR_CHAMP_FAMILY,)
# leftover-cone-region + winning_ir_region: inspect loops (cap 4), not one-shot.
STAGES_IR_INSPECT = (STAGE_IR_INSPECT,)
# depth 0 only. Depth ≥ 1 stays run_next_refine in the controller.
STAGES_IR_REGION_CELL = (STAGE_WINNING_IR_REGION_CELL,)
# champ AMG/RAS/Krylov + static IR/mesh/straps + EM. After refine while.
STAGES_IR_SOLVERS = (STAGE_IR_SOLVERS,)

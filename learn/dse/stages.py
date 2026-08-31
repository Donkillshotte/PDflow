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
    """Pay at most this stage. ``stage.run`` owns should_pay + evaluate."""
    return bool(stage.run(ctx))


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
) -> bool:
    step = ctx["step"]
    plan = ctx["plan"]
    t_end = ctx["t_end"]
    mem = ctx["mem"]
    if acquire_fidelity:
        extra = dict(acquire_extra or {})
        step("acquire", fidelity=acquire_fidelity, pay=pay, why=why, **extra)
    if not planned(plan, level) or not pay or time.time() >= t_end:
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
    return evaluate()


def run_f2_fast(ctx: dict) -> bool:
    from .acquire import should_pay_f2_fast
    from .fidelity import evaluate_f2_fast

    mem = ctx["mem"]
    n_f2 = 0
    pay, why = should_pay_f2_fast(mem, n_f2=n_f2)

    def _eval() -> bool:
        nonlocal n_f2
        winners = list(ctx["f1_pareto_parents"](mem))
        seen = {c.id for c in winners}
        extra = [c for c in ctx["f1_ok"](mem) if c.id not in seen]
        extra.sort(key=lambda c: float(c.qor.area_um2))
        winners.extend(extra)
        paid = False
        for w in winners:
            if n_f2 >= 4 or time.time() >= ctx["t_end"]:
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
    pay, why = should_pay_f2_gpl(
        mem, budget_left=ctx["t_end"] - time.time(), n_gpl=n_gpl, min_s=min_s
    )

    def _eval() -> bool:
        pick = ctx["mapped_pick"](
            [ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            rtl=ctx["rtl"],
            liberty=ctx["liberty"],
            top=ctx["top"],
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
    pay, why = should_pay_f3_sta(
        mem, budget_left=ctx["t_end"] - time.time(), n_sta=n_sta, min_s=min_s
    )

    def _eval() -> bool:
        ranked = [
            c
            for c in mem.all()
            if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None
        ]
        ranked.sort(key=lambda c: float(c.qor.area_um2))
        paid = False
        for w in ranked[:4]:
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
    pay, why = should_pay_f3_sdf(
        mem, budget_left=ctx["t_end"] - time.time(), n_sdf=n_sdf, min_s=min_s
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
    pay, why = should_pay_f2_grt(
        mem, budget_left=ctx["t_end"] - time.time(), n_grt=n_grt, min_s=min_s
    )

    def _eval() -> bool:
        pick = ctx["mapped_pick"](
            [ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            rtl=ctx["rtl"],
            liberty=ctx["liberty"],
            top=ctx["top"],
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
    pay, why = should_pay_f5_drt(
        mem, budget_left=ctx["t_end"] - time.time(), n_f5=n_f5, min_s=min_s
    )

    def _eval() -> bool:
        pick = ctx["mapped_pick"](
            [ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            rtl=ctx["rtl"],
            liberty=ctx["liberty"],
            top=ctx["top"],
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
    pay, why = should_pay_f3_spef(
        mem, budget_left=ctx["t_end"] - time.time(), n_spef=n_spef, min_s=min_s
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
    pay, why = should_pay_f5_cts(
        mem, budget_left=ctx["t_end"] - time.time(), n_f5_cts=n_f5_cts, min_s=min_s
    )

    def _eval() -> bool:
        pick = ctx["mapped_pick"](
            [ctx["f1_area_winner"](mem)] + [c for c in ctx["f1_ok"](mem)],
            rtl=ctx["rtl"],
            liberty=ctx["liberty"],
            top=ctx["top"],
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
    pay, why = should_pay_f5_local(
        mem, budget_left=ctx["t_end"] - time.time(), n_f5_local=n_f5_local, min_s=min_s
    )
    hosts_ord, host_why = order_local_hosts(mem)

    def _eval() -> bool:
        from .acquire import local_hosts

        child = None
        host = None
        for cand in hosts_ord or local_hosts(mem):
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
    pay, why = should_pay_f5_port(
        mem, budget_left=ctx["t_end"] - time.time(), n_f5_port=n_f5_port, min_s=min_s
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

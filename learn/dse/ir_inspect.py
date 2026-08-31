"""C5: leftover-cone-region and winning-IR-region inspect loops.

Closed-loop inspect (kind ∈ {extract, pdn}), not a one-shot Stage.
why / via / step strings stay identical to the inlined controller.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class InspectLoop:
    next_fn: Callable[..., dict | None]
    plan_extract: str
    plan_pdn: str
    extract_fidelity: str
    pdn_fidelity: str
    deny_why: str
    host_fn: Callable[[Any], Any]
    extract_kind: str
    extract_via: str
    pdn_via: str
    max_iters: int = 4


def run_inspect_loop(ctx: dict, spec: InspectLoop) -> bool:
    """Pay extract or |Δ| PDN until inspector returns None / wall / cap.

    Not a one-shot Stage: first empty inspect still emits the denied acquire.
    """
    mem = ctx["mem"]
    plan = ctx["plan"]
    t_end = ctx["t_end"]
    step = ctx["step"]
    variant = ctx["variant"]
    design_id = ctx["design_id"]
    evaluate_f4_extract = ctx["evaluate_f4_extract"]
    evaluate_f4_pdn = ctx["evaluate_f4_pdn"]
    persist_hotspot_join = ctx["persist_hotspot_join"]
    flowlab_params = ctx["flowlab_params"]
    gpl_density = ctx["gpl_density"]
    from .acquire import extract_on_disk
    from .active import winning_host_pdn

    plan_ex = any(s["level"] == spec.plan_extract for s in plan["steps"])
    plan_pdn = any(s["level"] == spec.plan_pdn for s in plan["steps"])
    for i in range(spec.max_iters):
        nxt = spec.next_fn(mem, budget_left=t_end - time.time())
        if not nxt or time.time() >= t_end:
            if i == 0:
                step(
                    "acquire",
                    fidelity=spec.extract_fidelity,
                    pay=False,
                    why=spec.deny_why,
                )
            break
        kind = nxt.get("kind")
        steer = nxt.get("steer") or {}
        why = nxt.get("why")
        if kind == "extract" and plan_ex:
            step(
                "acquire",
                fidelity=spec.extract_fidelity,
                pay=True,
                why=why,
                steer=steer,
                loop=i,
            )
            host = spec.host_fn(mem)
            if host and (host.artifacts or {}).get("mapped_v"):
                params = flowlab_params()
                util = float(params.get("coreUtilization") or 35.0)
                den = gpl_density(util, params.get("placeDensityAddon") or 0.2)
                child = evaluate_f4_extract(
                    host,
                    mem,
                    design_id=design_id,
                    variant=variant,
                    util=util,
                    density=den,
                    kind=spec.extract_kind,
                    region=steer.get("region"),
                    x_dbu=steer.get("x_dbu"),
                    y_dbu=steer.get("y_dbu"),
                    region_density=0.30,
                )
                if child:
                    persist_hotspot_join(child)
                    mem.touch(child)
                    step(
                        "evaluate",
                        id=child.id,
                        level="pdn",
                        fidelity="F4",
                        via=spec.extract_via,
                        parent=host.id,
                        parent_extract_id=steer.get("extract_id"),
                        region=steer.get("region"),
                        n_r=(child.artifacts or {}).get("n_r"),
                        droop_mv=child.qor.dynamic_ir_mv,
                        residual_mv=(child.attr or {}).get("residual_mv"),
                        gold=False,
                        status=child.status,
                        reason=steer.get("reason"),
                    )
            continue
        if kind == "pdn" and plan_pdn:
            step(
                "acquire",
                fidelity=spec.pdn_fidelity,
                pay=True,
                why=why,
                steer=steer,
                loop=i,
            )
            spec_pdn = steer.get("spec") or {}
            eid = str(steer.get("extract_id") or "")
            hit = extract_on_disk(mem, eid) if eid else None
            if spec_pdn and hit:
                child = evaluate_f4_pdn(
                    mem,
                    spec_pdn,
                    variant=variant,
                    design_id=design_id,
                    parent_id=hit["candidate"].id,
                    spice=hit["spice"],
                    insts=hit["insts"],
                    extract_id=eid,
                    sta=hit.get("sta"),
                )
                if child:
                    child.attr = dict(child.attr or {})
                    child.attr["via"] = spec.pdn_via
                    child.attr["steer"] = {k: steer[k] for k in steer if k != "spec"}
                    host_win = winning_host_pdn(mem)
                    if host_win and host_win.qor.dynamic_ir_mv is not None and child.qor.dynamic_ir_mv is not None:
                        child.attr["residual_vs_host_win_mv"] = float(child.qor.dynamic_ir_mv) - float(
                            host_win.qor.dynamic_ir_mv
                        )
                        child.attr["residual_vs_host_win"] = host_win.id
                    mem.touch(child)
                    step(
                        "evaluate",
                        id=child.id,
                        level="pdn",
                        fidelity="F4",
                        via=spec.pdn_via,
                        parent=hit["candidate"].id,
                        catalog=spec_pdn.get("name"),
                        extract_id=eid,
                        region=steer.get("region"),
                        droop_mv=child.qor.dynamic_ir_mv,
                        residual_vs_host_win_mv=(child.attr or {}).get("residual_vs_host_win_mv"),
                        gold=False,
                        status=child.status,
                        reason=steer.get("reason"),
                    )
            continue
        break
    return True


def run_ir_inspect_loops(ctx: dict) -> bool:
    from .acquire import leftover_cone_region_next, winning_ir_region_next
    from .active import ir_cell_champ_cone_host, ir_cell_host

    run_inspect_loop(
        ctx,
        InspectLoop(
            next_fn=leftover_cone_region_next,
            plan_extract="ir_cell_champ_cone_region",
            plan_pdn="ir_cell_champ_cone_region_pdn",
            extract_fidelity="F4_IR_CELL_CHAMP_CONE_REGION",
            pdn_fidelity="IR_CELL_CHAMP_CONE_REGION_PDN",
            deny_why="no leftover-cone-region extract or |Δ| PDN",
            host_fn=ir_cell_champ_cone_host,
            extract_kind="ir_cell_champ_cone_region",
            extract_via="f4_ir_cell_champ_cone_region_extract",
            pdn_via="active_f4_ir_cell_champ_cone_region_pdn",
        ),
    )
    run_inspect_loop(
        ctx,
        InspectLoop(
            next_fn=winning_ir_region_next,
            plan_extract="winning_ir_region",
            plan_pdn="winning_ir_region_pdn",
            extract_fidelity="F4_WINNING_IR_REGION",
            pdn_fidelity="WINNING_IR_REGION_PDN",
            deny_why="no winning-IR-region extract or |Δ| PDN",
            host_fn=ir_cell_host,
            extract_kind="winning_ir_region",
            extract_via="f4_winning_ir_region_extract",
            pdn_via="active_f4_winning_ir_region_pdn",
        ),
    )
    return True

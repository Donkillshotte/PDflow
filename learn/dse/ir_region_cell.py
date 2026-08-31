"""C6: winning_ir_region_cell depth 0 (size / extract / PDN).

Depth ≥ 1 stays dispatch.run_next_refine immediately after this family.
why / via / step strings stay identical to the inlined controller.
"""
from __future__ import annotations

import time


def run_winning_ir_region_cell(ctx: dict) -> bool:
    from .acquire import (
        extract_on_disk,
        should_pay_winning_ir_region_cell,
        should_pay_winning_ir_region_cell_extract,
        should_pay_winning_ir_region_cell_pdn,
    )
    from .active import (
        ir_cell_host,
        steer_from_winning_ir_region_cell_residual,
        steer_from_winning_ir_region_pdn_hotspot,
        winning_host_pdn,
        winning_ir_region_cell_host,
    )
    from .fidelity import evaluate_cell_size

    mem = ctx["mem"]
    plan = ctx["plan"]
    t_end = ctx["t_end"]
    step = ctx["step"]
    variant = ctx["variant"]
    design_id = ctx["design_id"]
    rtl = ctx["rtl"]
    lib = ctx["liberty"]
    top = ctx["top"]
    evaluate_f4_pdn = ctx["evaluate_f4_pdn"]
    evaluate_f4_extract = ctx["evaluate_f4_extract"]
    ensure_mapped_netlist = ctx["ensure_mapped_netlist"]
    flowlab_params = ctx["flowlab_params"]
    gpl_density = ctx["gpl_density"]
    persist_hotspot_join = ctx["persist_hotspot_join"]

    steer_wirc = steer_from_winning_ir_region_pdn_hotspot(mem)
    _wirc_eid = str((steer_wirc or {}).get("extract_id") or "")
    n_wirc = sum(
        1
        for c in mem.by_level("cell")
        if (c.knobs or {}).get("source") == "cell_size_ir_winning_region"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == _wirc_eid
    )
    pay_wirc, why_wirc = should_pay_winning_ir_region_cell(
        mem, budget_left=t_end - time.time(), steer=steer_wirc, n_cell=n_wirc
    )
    step("acquire", fidelity="WINNING_IR_REGION_CELL", pay=pay_wirc, why=why_wirc, steer=steer_wirc)
    if (
        any(s["level"] == "winning_ir_region_cell" for s in plan["steps"])
        and pay_wirc
        and steer_wirc
        and time.time() < t_end
    ):
        host_wirc = ir_cell_host(mem)
        cells_wirc = list(steer_wirc.get("cells") or [])
        if host_wirc and cells_wirc:
            if not (host_wirc.artifacts or {}).get("mapped_v"):
                host_wirc = ensure_mapped_netlist(host_wirc, rtl=rtl, liberty=lib, top=top)
                mem.touch(host_wirc)
            child = evaluate_cell_size(
                host_wirc,
                mem,
                design_id=design_id,
                cells=cells_wirc,
                source="cell_size_ir_winning_region",
                extract_id=_wirc_eid or None,
            )
            if child:
                step(
                    "evaluate",
                    id=child.id,
                    level="cell",
                    fidelity="F3",
                    via="active_f4_winning_ir_region_cell",
                    parent=host_wirc.id,
                    modules=steer_wirc.get("modules"),
                    extract_id=_wirc_eid,
                    region=steer_wirc.get("region"),
                    n_changed=(child.artifacts or {}).get("n_changed"),
                    wns_ns=(child.artifacts or {}).get("wns_ns"),
                    area_um2=child.qor.area_um2,
                    gold=False,
                    status=child.status,
                    reason=why_wirc,
                )

    host_wirce_pre = winning_ir_region_cell_host(mem)
    _wirce_eid = str((host_wirce_pre.knobs or {}).get("extract_id") or "") if host_wirce_pre else ""
    n_wirce = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_extract"
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == _wirce_eid
    )
    pay_wirce, why_wirce = should_pay_winning_ir_region_cell_extract(
        mem, budget_left=t_end - time.time(), n_extract=n_wirce
    )
    step("acquire", fidelity="F4_WINNING_IR_REGION_CELL_EXTRACT", pay=pay_wirce, why=why_wirce)
    if (
        any(s["level"] == "winning_ir_region_cell_extract" for s in plan["steps"])
        and pay_wirce
        and time.time() < t_end
    ):
        host_wirce = winning_ir_region_cell_host(mem)
        if host_wirce and (host_wirce.artifacts or {}).get("mapped_v"):
            params = flowlab_params()
            util_wirce = float(params.get("coreUtilization") or 35.0)
            den_wirce = gpl_density(util_wirce, params.get("placeDensityAddon") or 0.2)
            child = evaluate_f4_extract(
                host_wirce,
                mem,
                design_id=design_id,
                variant=variant,
                util=util_wirce,
                density=den_wirce,
                kind="winning_ir_region_cell",
            )
            if child:
                persist_hotspot_join(child)
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="f4_winning_ir_region_cell_extract",
                    parent=host_wirce.id,
                    parent_extract_id=_wirce_eid,
                    n_r=(child.artifacts or {}).get("n_r"),
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_mv=(child.attr or {}).get("residual_mv"),
                    gold=False,
                    status=child.status,
                    reason=why_wirce,
                )

    steer_wircp = steer_from_winning_ir_region_cell_residual(mem)
    _wircp_eid = str((steer_wircp or {}).get("extract_id") or "")
    n_wircp = sum(
        1
        for c in mem.all()
        if (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_pdn"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == _wircp_eid
    )
    pay_wircp, why_wircp = should_pay_winning_ir_region_cell_pdn(
        mem, budget_left=t_end - time.time(), steer=steer_wircp, n_steer=n_wircp
    )
    step("acquire", fidelity="WINNING_IR_REGION_CELL_PDN", pay=pay_wircp, why=why_wircp, steer=steer_wircp)
    if (
        any(s["level"] == "winning_ir_region_cell_pdn" for s in plan["steps"])
        and pay_wircp
        and steer_wircp
        and time.time() < t_end
    ):
        spec_wircp = steer_wircp.get("spec") or {}
        eid_wircp = str(steer_wircp.get("extract_id") or "")
        hit_wircp = extract_on_disk(mem, eid_wircp) if eid_wircp else None
        if spec_wircp and hit_wircp:
            child = evaluate_f4_pdn(
                mem,
                spec_wircp,
                variant=variant,
                design_id=design_id,
                parent_id=hit_wircp["candidate"].id,
                spice=hit_wircp["spice"],
                insts=hit_wircp["insts"],
                extract_id=eid_wircp,
                sta=hit_wircp.get("sta"),
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "active_f4_winning_ir_region_cell_pdn"
                child.attr["steer"] = {k: steer_wircp[k] for k in steer_wircp if k != "spec"}
                host_win = winning_host_pdn(mem)
                if host_win and host_win.qor.dynamic_ir_mv is not None and child.qor.dynamic_ir_mv is not None:
                    child.attr["residual_vs_host_win_mv"] = float(child.qor.dynamic_ir_mv) - float(
                        host_win.qor.dynamic_ir_mv
                    )
                    child.attr["residual_vs_host_win"] = host_win.id
                persist_hotspot_join(child)
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="active_f4_winning_ir_region_cell_pdn",
                    parent=hit_wircp["candidate"].id,
                    catalog=spec_wircp.get("name"),
                    extract_id=eid_wircp,
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_host_win_mv=(child.attr or {}).get("residual_vs_host_win_mv"),
                    gold=False,
                    status=child.status,
                    reason=steer_wircp.get("reason"),
                )
    return True

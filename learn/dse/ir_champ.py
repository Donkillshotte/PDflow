"""C4: winning_ir catalog + I-scale champ + ir_cell_champ/cone family.

Moved verbatim from run_controller. why/via/step strings stay identical.
"""
from __future__ import annotations

import time


def run_ir_champ_family(ctx: dict) -> bool:
    from .acquire import (
        extract_on_disk,
        iscale_champ_sta,
        should_pay_f4_scale_champ,
        should_pay_ir_cell_champ,
        should_pay_ir_cell_champ_cone,
        should_pay_ir_cell_champ_cone_extract,
        should_pay_ir_cell_champ_cone_pdn,
        should_pay_ir_cell_champ_extract,
        should_pay_ir_cell_champ_pdn,
        should_pay_winning_ir_catalog,
    )
    from .active import (
        ir_cell_champ_cone_host,
        ir_cell_champ_host,
        ir_cell_host,
        steer_from_ir_cell_champ_cone_residual,
        steer_from_ir_cell_champ_extract_hotspot,
        steer_from_ir_cell_champ_residual,
        steer_from_iscale_champ_hotspot,
        steer_from_winning_ir_catalog,
        winning_host_pdn,
        winning_ir_pdn,
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
    timing_of = ctx["timing_of"]
    evaluate_f4_pdn = ctx["evaluate_f4_pdn"]
    evaluate_f4_scale = ctx["evaluate_f4_scale"]
    evaluate_f4_extract = ctx["evaluate_f4_extract"]
    ensure_mapped_netlist = ctx["ensure_mapped_netlist"]
    flowlab_params = ctx["flowlab_params"]
    gpl_density = ctx["gpl_density"]

    _wir = winning_ir_pdn(mem)
    _wir_eid = str((_wir.knobs or {}).get("extract_id") or _wir.id) if _wir else ""
    n_wir = sum(
        1
        for c in mem.by_level("pdn")
        if (c.attr or {}).get("via") == "active_f4_winning_ir_pdn"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == _wir_eid
    )
    steer_wir = steer_from_winning_ir_catalog(mem)
    pay_wir, why_wir = should_pay_winning_ir_catalog(
        mem, budget_left=t_end - time.time(), steer=steer_wir, n_steer=n_wir, variant=variant
    )
    step("acquire", fidelity="F4_WINNING_IR_PDN", pay=pay_wir, why=why_wir, steer=steer_wir)
    if (
        any(s["level"] == "winning_ir_pdn" for s in plan["steps"])
        and pay_wir
        and steer_wir
        and time.time() < t_end
    ):
        spec_wir = steer_wir.get("spec") or {}
        eid_wir = str(steer_wir.get("extract_id") or "")
        hit_wir = extract_on_disk(mem, eid_wir) if eid_wir else None
        host_w = winning_ir_pdn(mem)
        if spec_wir and hit_wir:
            child = evaluate_f4_pdn(
                mem,
                spec_wir,
                variant=variant,
                design_id=design_id,
                parent_id=hit_wir["candidate"].id,
                spice=hit_wir["spice"],
                insts=hit_wir["insts"],
                extract_id=eid_wir,
                sta=hit_wir.get("sta"),
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "active_f4_winning_ir_pdn"
                child.attr["steer"] = {k: steer_wir[k] for k in steer_wir if k != "spec"}
                if host_w and host_w.qor.dynamic_ir_mv is not None and child.qor.dynamic_ir_mv is not None:
                    child.attr["residual_vs_winning_ir_mv"] = float(child.qor.dynamic_ir_mv) - float(
                        host_w.qor.dynamic_ir_mv
                    )
                    child.attr["residual_vs_winning_ir"] = host_w.id
                child.attr["residual_via"] = "winning_ir_catalog_vs_champ"
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="active_f4_winning_ir_pdn",
                    parent=hit_wir["candidate"].id,
                    catalog=spec_wir.get("name"),
                    extract_id=eid_wir,
                    pkg_r=spec_wir.get("pkg_r"),
                    pkg_l=spec_wir.get("pkg_l"),
                    c_decap=spec_wir.get("c_decap"),
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_winning_ir_mv=(child.attr or {}).get("residual_vs_winning_ir_mv"),
                    gold=False,
                    status=child.status,
                    reason=steer_wir.get("reason"),
                )

    _isc_champ = winning_ir_pdn(mem)
    _isc_eid = str((_isc_champ.knobs or {}).get("extract_id") or _isc_champ.id) if _isc_champ else ""
    n_sc = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_iscale_champ"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == _isc_eid
    )
    pay_sch, why_sch = should_pay_f4_scale_champ(
        mem, budget_left=t_end - time.time(), n_scale=n_sc, variant=variant
    )
    step("acquire", fidelity="F4_ISCALE_CHAMP", pay=pay_sch, why=why_sch)
    if any(s["level"] == "f4_scale_champ" for s in plan["steps"]) and pay_sch and time.time() < t_end:
        base_p_c = None
        for c in mem.by_level("logic"):
            if c.status == "ok" and c.knobs.get("name") == "liberty_default":
                _w, p = timing_of(mem, c)
                if p:
                    base_p_c = p
                    break
        pick_c = ir_cell_host(mem)
        champ = winning_ir_pdn(mem)
        eid_c = str((champ.knobs or {}).get("extract_id") or champ.id) if champ else ""
        hit_c = extract_on_disk(mem, eid_c) if eid_c else None
        sta_c, via_c = iscale_champ_sta(hit_c)
        if pick_c and base_p_c and champ and hit_c and via_c != "f4_host_arrivals":
            child = evaluate_f4_scale(
                pick_c,
                mem,
                variant=variant,
                design_id=design_id,
                baseline_power_w=base_p_c,
                pkg_r=float((champ.knobs or {}).get("pkg_r") or 0.05),
                pkg_l=float((champ.knobs or {}).get("pkg_l") or 2e-10),
                c_decap=float((champ.knobs or {}).get("c_decap") or 50e-15),
                spice=hit_c["spice"],
                insts=hit_c["insts"],
                extract_id=eid_c,
                sta=sta_c,
                sta_via=via_c,
                source="f4_iscale_champ",
            )
            if child:
                host_win = winning_host_pdn(mem)
                isw = next(
                    (
                        c
                        for c in reversed(list(mem.by_level("pdn")))
                        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_iscale_win"
                    ),
                    None,
                )
                child.attr = dict(child.attr or {})
                if host_win and host_win.qor.dynamic_ir_mv is not None:
                    child.attr["residual_vs_host_win_mv"] = float(child.qor.dynamic_ir_mv or 0.0) - float(
                        host_win.qor.dynamic_ir_mv
                    )
                    child.attr["residual_vs_host_win"] = host_win.id
                if isw and isw.qor.dynamic_ir_mv is not None and child.qor.dynamic_ir_mv is not None:
                    child.attr["residual_vs_iscale_win_mv"] = float(child.qor.dynamic_ir_mv) - float(
                        isw.qor.dynamic_ir_mv
                    )
                    child.attr["residual_vs_iscale_win"] = isw.id
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="f4_iscale_champ",
                    parent=pick_c.id,
                    host_level=pick_c.level,
                    host_source=(pick_c.knobs or {}).get("source") or pick_c.level,
                    champ_source=(champ.knobs or {}).get("name") or (champ.attr or {}).get("via"),
                    i_scale=(child.knobs or {}).get("i_scale"),
                    extract_id=eid_c,
                    c_decap=(child.knobs or {}).get("c_decap"),
                    sta_via=via_c,
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_iscale_win_mv=(child.attr or {}).get("residual_vs_iscale_win_mv"),
                    gold=False,
                    status=child.status,
                    reason=why_sch,
                )

    steer_icc = steer_from_iscale_champ_hotspot(mem)
    _icc_eid = str((steer_icc or {}).get("extract_id") or "")
    n_icc = sum(
        1
        for c in mem.by_level("cell")
        if (c.knobs or {}).get("source") == "cell_size_ir_champ"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == _icc_eid
    )
    pay_icc, why_icc = should_pay_ir_cell_champ(
        mem, budget_left=t_end - time.time(), steer=steer_icc, n_cell=n_icc
    )
    step("acquire", fidelity="IR_CELL_CHAMP", pay=pay_icc, why=why_icc, steer=steer_icc)
    if any(s["level"] == "ir_cell_champ" for s in plan["steps"]) and pay_icc and steer_icc and time.time() < t_end:
        host_icc = ir_cell_host(mem)
        cells_icc = list(steer_icc.get("cells") or [])
        if host_icc and cells_icc:
            if not (host_icc.artifacts or {}).get("mapped_v"):
                host_icc = ensure_mapped_netlist(host_icc, rtl=rtl, liberty=lib, top=top)
                mem.touch(host_icc)
            child = evaluate_cell_size(
                host_icc,
                mem,
                design_id=design_id,
                cells=cells_icc,
                source="cell_size_ir_champ",
                extract_id=_icc_eid or None,
            )
            if child:
                step(
                    "evaluate",
                    id=child.id,
                    level="cell",
                    fidelity="F3",
                    via="active_f4_ir_cell_champ",
                    parent=host_icc.id,
                    modules=steer_icc.get("modules"),
                    extract_id=_icc_eid,
                    region=steer_icc.get("region"),
                    n_changed=(child.artifacts or {}).get("n_changed"),
                    wns_ns=(child.artifacts or {}).get("wns_ns"),
                    area_um2=child.qor.area_um2,
                    gold=False,
                    status=child.status,
                    reason=why_icc,
                )

    host_icce_pre = ir_cell_champ_host(mem)
    _icce_eid = str((host_icce_pre.knobs or {}).get("extract_id") or "") if host_icce_pre else ""
    n_icce = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_ir_cell_champ_extract"
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == _icce_eid
    )
    pay_icce, why_icce = should_pay_ir_cell_champ_extract(
        mem, budget_left=t_end - time.time(), n_extract=n_icce
    )
    step("acquire", fidelity="F4_IR_CELL_CHAMP_EXTRACT", pay=pay_icce, why=why_icce)
    if any(s["level"] == "ir_cell_champ_extract" for s in plan["steps"]) and pay_icce and time.time() < t_end:
        host_icce = ir_cell_champ_host(mem)
        if host_icce and (host_icce.artifacts or {}).get("mapped_v"):
            params = flowlab_params()
            util_icce = float(params.get("coreUtilization") or 35.0)
            den_icce = gpl_density(util_icce, params.get("placeDensityAddon") or 0.2)
            child = evaluate_f4_extract(
                host_icce,
                mem,
                design_id=design_id,
                variant=variant,
                util=util_icce,
                density=den_icce,
                kind="ir_cell_champ",
            )
            if child:
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="f4_ir_cell_champ_extract",
                    parent=host_icce.id,
                    parent_extract_id=_icce_eid,
                    host_source=(host_icce.knobs or {}).get("source") or host_icce.level,
                    n_r=(child.artifacts or {}).get("n_r"),
                    n_sta=(child.artifacts or {}).get("n_sta_inst"),
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_mv=(child.attr or {}).get("residual_mv"),
                    gold=False,
                    status=child.status,
                    reason=why_icce,
                )

    steer_iccp = steer_from_ir_cell_champ_residual(mem)
    _iccp_eid = str((steer_iccp or {}).get("extract_id") or "")
    n_iccp = sum(
        1
        for c in mem.all()
        if (c.attr or {}).get("via") == "active_f4_ir_cell_champ_pdn"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == _iccp_eid
    )
    pay_iccp, why_iccp = should_pay_ir_cell_champ_pdn(
        mem, budget_left=t_end - time.time(), steer=steer_iccp, n_steer=n_iccp
    )
    step("acquire", fidelity="IR_CELL_CHAMP_PDN", pay=pay_iccp, why=why_iccp, steer=steer_iccp)
    if (
        any(s["level"] == "ir_cell_champ_pdn" for s in plan["steps"])
        and pay_iccp
        and steer_iccp
        and time.time() < t_end
    ):
        spec_iccp = steer_iccp.get("spec") or {}
        eid_iccp = str(steer_iccp.get("extract_id") or "")
        hit_iccp = extract_on_disk(mem, eid_iccp) if eid_iccp else None
        if spec_iccp and hit_iccp:
            child = evaluate_f4_pdn(
                mem,
                spec_iccp,
                variant=variant,
                design_id=design_id,
                parent_id=hit_iccp["candidate"].id,
                spice=hit_iccp["spice"],
                insts=hit_iccp["insts"],
                extract_id=eid_iccp,
                sta=hit_iccp.get("sta"),
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "active_f4_ir_cell_champ_pdn"
                child.attr["steer"] = {k: steer_iccp[k] for k in steer_iccp if k != "spec"}
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
                    via="active_f4_ir_cell_champ_pdn",
                    parent=hit_iccp["candidate"].id,
                    catalog=spec_iccp.get("name"),
                    extract_id=eid_iccp,
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_host_win_mv=(child.attr or {}).get("residual_vs_host_win_mv"),
                    gold=False,
                    status=child.status,
                    reason=steer_iccp.get("reason"),
                )

    steer_iccc = steer_from_ir_cell_champ_extract_hotspot(mem)
    _iccc_eid = str((steer_iccc or {}).get("extract_id") or "")
    n_iccc = sum(
        1
        for c in mem.by_level("cell")
        if (c.knobs or {}).get("source") == "cell_size_ir_champ_cone"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == _iccc_eid
    )
    pay_iccc, why_iccc = should_pay_ir_cell_champ_cone(
        mem, budget_left=t_end - time.time(), steer=steer_iccc, n_cell=n_iccc
    )
    step("acquire", fidelity="IR_CELL_CHAMP_CONE", pay=pay_iccc, why=why_iccc, steer=steer_iccc)
    if any(s["level"] == "ir_cell_champ_cone" for s in plan["steps"]) and pay_iccc and steer_iccc and time.time() < t_end:
        host_iccc = ir_cell_champ_host(mem)
        cells_iccc = list(steer_iccc.get("cells") or [])
        if host_iccc and cells_iccc:
            if not (host_iccc.artifacts or {}).get("mapped_v"):
                host_iccc = ensure_mapped_netlist(host_iccc, rtl=rtl, liberty=lib, top=top)
                mem.touch(host_iccc)
            child = evaluate_cell_size(
                host_iccc,
                mem,
                design_id=design_id,
                cells=cells_iccc,
                source="cell_size_ir_champ_cone",
                extract_id=_iccc_eid or None,
            )
            if child:
                step(
                    "evaluate",
                    id=child.id,
                    level="cell",
                    fidelity="F3",
                    via="active_f4_ir_cell_champ_cone",
                    parent=host_iccc.id,
                    modules=steer_iccc.get("modules"),
                    extract_id=_iccc_eid,
                    region=steer_iccc.get("region"),
                    n_changed=(child.artifacts or {}).get("n_changed"),
                    wns_ns=(child.artifacts or {}).get("wns_ns"),
                    area_um2=child.qor.area_um2,
                    gold=False,
                    status=child.status,
                    reason=why_iccc,
                )

    host_iccce_pre = ir_cell_champ_cone_host(mem)
    _iccce_eid = str((host_iccce_pre.knobs or {}).get("extract_id") or "") if host_iccce_pre else ""
    n_iccce = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_extract"
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == _iccce_eid
    )
    pay_iccce, why_iccce = should_pay_ir_cell_champ_cone_extract(
        mem, budget_left=t_end - time.time(), n_extract=n_iccce
    )
    step("acquire", fidelity="F4_IR_CELL_CHAMP_CONE_EXTRACT", pay=pay_iccce, why=why_iccce)
    if any(s["level"] == "ir_cell_champ_cone_extract" for s in plan["steps"]) and pay_iccce and time.time() < t_end:
        host_iccce = ir_cell_champ_cone_host(mem)
        if host_iccce and (host_iccce.artifacts or {}).get("mapped_v"):
            params = flowlab_params()
            util_iccce = float(params.get("coreUtilization") or 35.0)
            den_iccce = gpl_density(util_iccce, params.get("placeDensityAddon") or 0.2)
            child = evaluate_f4_extract(
                host_iccce,
                mem,
                design_id=design_id,
                variant=variant,
                util=util_iccce,
                density=den_iccce,
                kind="ir_cell_champ_cone",
            )
            if child:
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="f4_ir_cell_champ_cone_extract",
                    parent=host_iccce.id,
                    parent_extract_id=_iccce_eid,
                    host_source=(host_iccce.knobs or {}).get("source") or host_iccce.level,
                    n_r=(child.artifacts or {}).get("n_r"),
                    n_sta=(child.artifacts or {}).get("n_sta_inst"),
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_mv=(child.attr or {}).get("residual_mv"),
                    gold=False,
                    status=child.status,
                    reason=why_iccce,
                )

    steer_icccp = steer_from_ir_cell_champ_cone_residual(mem)
    _icccp_eid = str((steer_icccp or {}).get("extract_id") or "")
    n_icccp = sum(
        1
        for c in mem.all()
        if (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_pdn"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == _icccp_eid
    )
    pay_icccp, why_icccp = should_pay_ir_cell_champ_cone_pdn(
        mem, budget_left=t_end - time.time(), steer=steer_icccp, n_steer=n_icccp
    )
    step("acquire", fidelity="IR_CELL_CHAMP_CONE_PDN", pay=pay_icccp, why=why_icccp, steer=steer_icccp)
    if (
        any(s["level"] == "ir_cell_champ_cone_pdn" for s in plan["steps"])
        and pay_icccp
        and steer_icccp
        and time.time() < t_end
    ):
        spec_icccp = steer_icccp.get("spec") or {}
        eid_icccp = str(steer_icccp.get("extract_id") or "")
        hit_icccp = extract_on_disk(mem, eid_icccp) if eid_icccp else None
        if spec_icccp and hit_icccp:
            child = evaluate_f4_pdn(
                mem,
                spec_icccp,
                variant=variant,
                design_id=design_id,
                parent_id=hit_icccp["candidate"].id,
                spice=hit_icccp["spice"],
                insts=hit_icccp["insts"],
                extract_id=eid_icccp,
                sta=hit_icccp.get("sta"),
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "active_f4_ir_cell_champ_cone_pdn"
                child.attr["steer"] = {k: steer_icccp[k] for k in steer_icccp if k != "spec"}
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
                    via="active_f4_ir_cell_champ_cone_pdn",
                    parent=hit_icccp["candidate"].id,
                    catalog=spec_icccp.get("name"),
                    extract_id=eid_icccp,
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_host_win_mv=(child.attr or {}).get("residual_vs_host_win_mv"),
                    gold=False,
                    status=child.status,
                    reason=steer_icccp.get("reason"),
                )
    return True

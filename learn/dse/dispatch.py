"""Execute the next refine-chain stage. Depth is a parameter, not a new block.

The controller calls `run_next_refine` in a loop. Each call pays at most one
stage (sizeup / extract / pdn / catalog) using the generic actions from
`actions.py`. Deeper leftovers need zero new controller code.
"""

from __future__ import annotations

from .actions import (
    should_pay_refine_catalog,
    should_pay_refine_extract,
    should_pay_refine_pdn,
    should_pay_refine_sizeup,
    steer_refine_catalog,
    steer_refine_pdn,
    steer_refine_sizeup,
)
from .frame import (
    _suffix,
    next_stage,
    refine_cell_source,
    refine_extract_source,
    refine_label,
)
from .memory import DesignMemory


def _cell_at(mem: DesignMemory, depth: int):
    """Newest ok size-up at this refine depth."""
    src = refine_cell_source(depth)
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == src:
            return c
    return None


def _sizeup_parent(mem: DesignMemory, depth: int):
    """Netlist the depth-N size-up edits: IR-cell host at 0, else depth N−1."""
    if depth <= 0:
        from .active import ir_cell_host

        return ir_cell_host(mem)
    return _cell_at(mem, depth - 1)


def run_next_refine(
    mem: DesignMemory,
    *,
    budget_left: float,
    plan_levels: set[str],
    design_id: str,
    variant: str,
    rtl,
    liberty,
    step,
    t_end: float,
    ensure_mapped_netlist,
    evaluate_cell_size,
    evaluate_f4_extract,
    evaluate_f4_pdn,
    extract_on_disk,
    persist_hotspot_join,
    flowlab_params,
    gpl_density,
    winning_host_pdn,
) -> bool:
    """Pay and evaluate the next refine stage. True if a child was recorded."""
    import time

    nxt = next_stage(mem)
    if nxt is None:
        step("acquire", fidelity="REFINE", pay=False, why="refine chain closed (leftover empty, catalog exhausted)")
        return False
    depth = int(nxt["depth"])
    stage = str(nxt["stage"])
    level_size = f"winning_ir_region_cell{_suffix(depth)}"
    level_ext = f"{level_size}_extract"
    level_pdn = f"{level_size}_pdn"
    level_cat = f"{level_size}_catalog"
    planned = plan_levels

    if stage == "sizeup":
        steer = steer_refine_sizeup(mem, depth)
        pay, why = should_pay_refine_sizeup(mem, depth=depth, budget_left=budget_left, steer=steer)
        step("acquire", fidelity=f"REFINE_{depth}_SIZEUP", pay=pay, why=why, steer=steer)
        if not (level_size in planned and pay and steer and time.time() < t_end):
            return False
        host = _sizeup_parent(mem, depth)
        cells = list(steer.get("cells") or [])
        if not host or not cells:
            return False
        if not (host.artifacts or {}).get("mapped_v"):
            host = ensure_mapped_netlist(host, rtl=rtl, liberty=liberty)
            mem.touch(host)
        child = evaluate_cell_size(
            host,
            mem,
            design_id=design_id,
            cells=cells,
            source=refine_cell_source(depth),
            extract_id=str(steer.get("extract_id") or "") or None,
        )
        if not child:
            return False
        step(
            "evaluate",
            id=child.id,
            level="cell",
            fidelity="F3",
            via=f"active_f4_winning_ir_region_cell{_suffix(depth)}",
            parent=host.id,
            modules=steer.get("modules"),
            n_changed=(child.artifacts or {}).get("n_changed"),
            depth=depth,
            gold=False,
            status=child.status,
            reason=steer.get("reason"),
        )
        return True

    if stage == "extract":
        pay, why = should_pay_refine_extract(mem, depth=depth, budget_left=budget_left)
        step("acquire", fidelity=f"REFINE_{depth}_EXTRACT", pay=pay, why=why)
        if not (level_ext in planned and pay and time.time() < t_end):
            return False
        host = _cell_at(mem, depth)
        if host is None:
            return False
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
            kind=f"winning_ir_region_cell{_suffix(depth)}",
        )
        if not child:
            return False
        persist_hotspot_join(child)
        mem.touch(child)
        step(
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via=refine_extract_source(depth),
            parent=host.id,
            n_r=(child.artifacts or {}).get("n_r"),
            droop_mv=child.qor.dynamic_ir_mv,
            residual_mv=(child.attr or {}).get("residual_mv"),
            depth=depth,
            gold=False,
            status=child.status,
            reason=why,
        )
        return True

    if stage == "pdn":
        steer = steer_refine_pdn(mem, depth)
        pay, why = should_pay_refine_pdn(mem, depth=depth, budget_left=budget_left, steer=steer)
        step("acquire", fidelity=f"REFINE_{depth}_PDN", pay=pay, why=why, steer=steer)
        if not (level_pdn in planned and pay and steer and time.time() < t_end):
            return False
        eid = str(steer.get("extract_id") or "")
        hit = extract_on_disk(mem, eid) if eid else None
        spec = steer.get("spec") or {}
        if not spec or not hit:
            return False
        child = evaluate_f4_pdn(
            mem,
            spec,
            variant=variant,
            design_id=design_id,
            parent_id=hit["candidate"].id,
            spice=hit["spice"],
            insts=hit["insts"],
            extract_id=eid,
            sta=hit.get("sta"),
        )
        if not child:
            return False
        child.attr = dict(child.attr or {})
        child.attr["via"] = f"active_f4_winning_ir_region_cell{_suffix(depth)}_pdn"
        child.attr["steer"] = {k: steer[k] for k in steer if k != "spec"}
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
            via=child.attr["via"],
            parent=hit["candidate"].id,
            catalog=spec.get("name"),
            extract_id=eid,
            droop_mv=child.qor.dynamic_ir_mv,
            residual_vs_host_win_mv=(child.attr or {}).get("residual_vs_host_win_mv"),
            depth=depth,
            gold=False,
            status=child.status,
            reason=steer.get("reason"),
        )
        return True

    if stage == "catalog":
        steer = steer_refine_catalog(mem, depth)
        n_steer = sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == f"active_f4_winning_ir_region_cell{_suffix(depth)}_catalog"
            and c.status == "ok"
            and str((c.knobs or {}).get("extract_id") or "") == str((steer or {}).get("extract_id") or "")
        )
        pay, why = should_pay_refine_catalog(
            mem, depth=depth, budget_left=budget_left, steer=steer, n_steer=n_steer
        )
        step("acquire", fidelity=f"REFINE_{depth}_CATALOG", pay=pay, why=why, steer=steer)
        if not (level_cat in planned and pay and steer and time.time() < t_end):
            return False
        eid = str(steer.get("extract_id") or "")
        hit = extract_on_disk(mem, eid) if eid else None
        spec = steer.get("spec") or {}
        if not spec or not hit:
            return False
        child = evaluate_f4_pdn(
            mem,
            spec,
            variant=variant,
            design_id=design_id,
            parent_id=hit["candidate"].id,
            spice=hit["spice"],
            insts=hit["insts"],
            extract_id=eid,
            sta=hit.get("sta"),
        )
        if not child:
            return False
        child.attr = dict(child.attr or {})
        child.attr["via"] = f"active_f4_winning_ir_region_cell{_suffix(depth)}_catalog"
        child.attr["steer"] = {k: steer[k] for k in steer if k != "spec"}
        host_pdn = None
        for c in reversed(list(mem.all())):
            if (
                c.status == "ok"
                and (c.attr or {}).get("via") == f"active_f4_winning_ir_region_cell{_suffix(depth)}_pdn"
                and str((c.knobs or {}).get("extract_id") or "") == eid
            ):
                host_pdn = c
                break
        if (
            host_pdn
            and host_pdn.qor.dynamic_ir_mv is not None
            and child.qor.dynamic_ir_mv is not None
        ):
            delta = float(child.qor.dynamic_ir_mv) - float(host_pdn.qor.dynamic_ir_mv)
            child.attr["residual_vs_refine_pdn_mv"] = delta
            child.attr["residual_vs_refine_pdn"] = host_pdn.id
            if depth == 2:
                child.attr["residual_vs_leftover2_pdn_mv"] = delta
                child.attr["residual_vs_leftover2_pdn"] = host_pdn.id
        child.attr["residual_via"] = (
            "leftover2_catalog_vs_leftover2_pdn" if depth == 2 else f"refine[{depth}]_catalog_vs_pdn"
        )
        persist_hotspot_join(child)
        mem.touch(child)
        step(
            "evaluate",
            id=child.id,
            level="pdn",
            fidelity="F4",
            via=child.attr["via"],
            parent=hit["candidate"].id,
            catalog=spec.get("name"),
            extract_id=eid,
            pkg_r=spec.get("pkg_r"),
            pkg_l=spec.get("pkg_l"),
            c_decap=spec.get("c_decap"),
            droop_mv=child.qor.dynamic_ir_mv,
            residual_vs_leftover2_pdn_mv=(child.attr or {}).get("residual_vs_leftover2_pdn_mv"),
            residual_vs_refine_pdn_mv=(child.attr or {}).get("residual_vs_refine_pdn_mv"),
            depth=depth,
            gold=False,
            status=child.status,
            reason=steer.get("reason"),
        )
        return True

    step("acquire", fidelity="REFINE", pay=False, why=f"unknown refine stage {stage} at {refine_label(depth)}")
    return False

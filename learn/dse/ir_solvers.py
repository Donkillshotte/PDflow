"""C7: champ AMG/RAS/Krylov + static IR/mesh/straps + EM.

Last IR-tail family. Krylov stays GCD-only via should_pay / admit_paid_f4.
why / via / step strings stay identical to the inlined controller.
"""
from __future__ import annotations

import time


def run_ir_solvers(ctx: dict) -> bool:
    from .acquire import (
        champ_mf_n,
        extract_on_disk,
        should_pay_em_straps,
        should_pay_f4_amg_champ,
        should_pay_f4_krylov_champ,
        should_pay_f4_ras_champ,
        should_pay_static_ir_steer,
        should_pay_static_mesh,
        should_pay_static_straps,
    )
    from .active import (
        steer_from_em_width_residual,
        steer_from_static_ir_residual,
        steer_from_static_mesh_residual,
        steer_from_static_strap_residual,
        strap_extract_host,
        winning_em_pdn,
        winning_ir_pdn,
        winning_static_pdn,
    )
    from .solve_result import residual_vs_reference_mv, stamp_f4_candidate

    mem = ctx["mem"]
    plan = ctx["plan"]
    t_end = ctx["t_end"]
    step = ctx["step"]
    variant = ctx["variant"]
    design_id = ctx["design_id"]
    evaluate_f4_pdn = ctx["evaluate_f4_pdn"]
    evaluate_f4_static_mesh = ctx["evaluate_f4_static_mesh"]
    evaluate_f4_static_straps = ctx["evaluate_f4_static_straps"]
    evaluate_f4_em_straps = ctx["evaluate_f4_em_straps"]

    n_amg_c = champ_mf_n(mem, "f4_solver_amg_champ")
    pay_amgc, why_amgc = should_pay_f4_amg_champ(
        mem, budget_left=t_end - time.time(), n_amg=n_amg_c, variant=variant
    )
    step("acquire", fidelity="F4_AMG_CHAMP", pay=pay_amgc, why=why_amgc)
    if any(s["level"] == "f4_amg_champ" for s in plan["steps"]) and pay_amgc and time.time() < t_end:
        champ_s = winning_ir_pdn(mem)
        eid_s = str((champ_s.knobs or {}).get("extract_id") or champ_s.id) if champ_s else ""
        hit_s = extract_on_disk(mem, eid_s) if eid_s else None
        if champ_s and hit_s:
            spec_amgc = {
                "name": "amg_champ",
                "pkg_r": float((champ_s.knobs or {}).get("pkg_r") or 0.05),
                "pkg_l": float((champ_s.knobs or {}).get("pkg_l") or 2e-10),
                "c_decap": float((champ_s.knobs or {}).get("c_decap") or 50e-15),
            }
            child = evaluate_f4_pdn(
                mem,
                spec_amgc,
                variant=variant,
                design_id=design_id,
                parent_id=hit_s["candidate"].id,
                spice=hit_s["spice"],
                insts=hit_s["insts"],
                extract_id=eid_s,
                solver="amg",
                sta=hit_s.get("sta"),
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "f4_solver_amg_champ"
                res = residual_vs_reference_mv(
                    child.artifacts,
                    fallback_child_mv=child.qor.dynamic_ir_mv,
                    fallback_ref_mv=champ_s.qor.dynamic_ir_mv,
                )
                if res is not None:
                    child.attr["residual_vs_direct_mv"] = res
                    child.attr["residual_vs_direct"] = champ_s.id
                    child.attr["residual_via"] = "amg_champ_vs_direct"
                stamp_f4_candidate(child)
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="f4_solver_amg_champ",
                    parent=hit_s["candidate"].id,
                    extract_id=eid_s,
                    c_decap=spec_amgc["c_decap"],
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_direct_mv=(child.attr or {}).get("residual_vs_direct_mv"),
                    gold=False,
                    status=child.status,
                    reason=why_amgc,
                )

    n_ras_c = champ_mf_n(mem, "f4_solver_ras_champ")
    pay_rasc, why_rasc = should_pay_f4_ras_champ(
        mem, budget_left=t_end - time.time(), n_ras=n_ras_c, variant=variant
    )
    step("acquire", fidelity="F4_RAS_CHAMP", pay=pay_rasc, why=why_rasc)
    if any(s["level"] == "f4_ras_champ" for s in plan["steps"]) and pay_rasc and time.time() < t_end:
        champ_s = winning_ir_pdn(mem)
        eid_s = str((champ_s.knobs or {}).get("extract_id") or champ_s.id) if champ_s else ""
        hit_s = extract_on_disk(mem, eid_s) if eid_s else None
        if champ_s and hit_s:
            spec_rasc = {
                "name": "ras_champ",
                "pkg_r": float((champ_s.knobs or {}).get("pkg_r") or 0.05),
                "pkg_l": float((champ_s.knobs or {}).get("pkg_l") or 2e-10),
                "c_decap": float((champ_s.knobs or {}).get("c_decap") or 50e-15),
            }
            child = evaluate_f4_pdn(
                mem,
                spec_rasc,
                variant=variant,
                design_id=design_id,
                parent_id=hit_s["candidate"].id,
                spice=hit_s["spice"],
                insts=hit_s["insts"],
                extract_id=eid_s,
                solver="ras",
                sta=hit_s.get("sta"),
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "f4_solver_ras_champ"
                res = residual_vs_reference_mv(
                    child.artifacts,
                    fallback_child_mv=child.qor.dynamic_ir_mv,
                    fallback_ref_mv=champ_s.qor.dynamic_ir_mv,
                )
                if res is not None:
                    child.attr["residual_vs_direct_mv"] = res
                    child.attr["residual_vs_direct"] = champ_s.id
                    child.attr["residual_via"] = "ras_champ_vs_direct"
                stamp_f4_candidate(child)
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="f4_solver_ras_champ",
                    parent=hit_s["candidate"].id,
                    extract_id=eid_s,
                    c_decap=spec_rasc["c_decap"],
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_direct_mv=(child.attr or {}).get("residual_vs_direct_mv"),
                    gold=False,
                    status=child.status,
                    reason=why_rasc,
                )

    n_kry_c = champ_mf_n(mem, "f4_solver_krylov_champ")
    pay_kryc, why_kryc = should_pay_f4_krylov_champ(
        mem, budget_left=t_end - time.time(), n_krylov=n_kry_c, variant=variant
    )
    step("acquire", fidelity="F4_KRYLOV_CHAMP", pay=pay_kryc, why=why_kryc)
    if any(s["level"] == "f4_krylov_champ" for s in plan["steps"]) and pay_kryc and time.time() < t_end:
        champ_s = winning_ir_pdn(mem)
        eid_s = str((champ_s.knobs or {}).get("extract_id") or champ_s.id) if champ_s else ""
        hit_s = extract_on_disk(mem, eid_s) if eid_s else None
        if champ_s and hit_s:
            spec_kryc = {
                "name": "krylov_champ",
                "pkg_r": float((champ_s.knobs or {}).get("pkg_r") or 0.05),
                "pkg_l": float((champ_s.knobs or {}).get("pkg_l") or 2e-10),
                "c_decap": float((champ_s.knobs or {}).get("c_decap") or 50e-15),
            }
            child = evaluate_f4_pdn(
                mem,
                spec_kryc,
                variant=variant,
                design_id=design_id,
                parent_id=hit_s["candidate"].id,
                spice=hit_s["spice"],
                insts=hit_s["insts"],
                extract_id=eid_s,
                solver="krylov",
                sta=hit_s.get("sta"),
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "f4_solver_krylov_champ"
                res = residual_vs_reference_mv(
                    child.artifacts,
                    fallback_child_mv=child.qor.dynamic_ir_mv,
                    fallback_ref_mv=champ_s.qor.dynamic_ir_mv,
                )
                if res is not None:
                    child.attr["residual_vs_direct_mv"] = res
                    child.attr["residual_vs_direct"] = champ_s.id
                    child.attr["residual_via"] = "krylov_champ_vs_direct"
                stamp_f4_candidate(child)
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="f4_solver_krylov_champ",
                    parent=hit_s["candidate"].id,
                    extract_id=eid_s,
                    c_decap=spec_kryc["c_decap"],
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_direct_mv=(child.attr or {}).get("residual_vs_direct_mv"),
                    gold=False,
                    status=child.status,
                    m=(child.artifacts or {}).get("m"),
                    reason=why_kryc,
                )

    n_sir = sum(
        1
        for c in mem.by_level("pdn")
        if (c.attr or {}).get("via") == "active_f4_static_ir" and c.status == "ok"
    )
    steer_sir = steer_from_static_ir_residual(mem)
    pay_sir, why_sir = should_pay_static_ir_steer(
        mem, budget_left=t_end - time.time(), steer=steer_sir, n_steer=n_sir, variant=variant
    )
    step("acquire", fidelity="F4_STATIC_IR", pay=pay_sir, why=why_sir, steer=steer_sir)
    if (
        any(s["level"] == "static_ir_steer" for s in plan["steps"])
        and pay_sir
        and steer_sir
        and time.time() < t_end
    ):
        spec_sir = steer_sir.get("spec") or {}
        eid_sir = str(steer_sir.get("extract_id") or "")
        hit_sir = extract_on_disk(mem, eid_sir) if eid_sir else None
        if spec_sir and hit_sir:
            host_s = winning_static_pdn(mem)
            host_d = winning_ir_pdn(mem)
            child = evaluate_f4_pdn(
                mem,
                spec_sir,
                variant=variant,
                design_id=design_id,
                parent_id=hit_sir["candidate"].id,
                spice=hit_sir["spice"],
                insts=hit_sir["insts"],
                extract_id=eid_sir,
                sta=hit_sir.get("sta"),
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "active_f4_static_ir"
                child.attr["steer"] = {k: steer_sir[k] for k in steer_sir if k != "spec"}
                if host_s and host_s.qor.static_ir_mv is not None and child.qor.static_ir_mv is not None:
                    child.attr["residual_vs_static_champ_mv"] = float(child.qor.static_ir_mv) - float(
                        host_s.qor.static_ir_mv
                    )
                    child.attr["residual_vs_static_champ"] = host_s.id
                if host_d and host_d.qor.dynamic_ir_mv is not None and child.qor.dynamic_ir_mv is not None:
                    child.attr["residual_vs_dynamic_champ_mv"] = float(child.qor.dynamic_ir_mv) - float(
                        host_d.qor.dynamic_ir_mv
                    )
                    child.attr["residual_vs_dynamic_champ"] = host_d.id
                child.attr["residual_via"] = "static_pkg_r_vs_static_champ"
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="active_f4_static_ir",
                    parent=hit_sir["candidate"].id,
                    catalog=spec_sir.get("name"),
                    extract_id=eid_sir,
                    pkg_r=spec_sir.get("pkg_r"),
                    static_ir_mv=child.qor.static_ir_mv,
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_static_champ_mv=(child.attr or {}).get("residual_vs_static_champ_mv"),
                    gold=False,
                    status=child.status,
                    reason=steer_sir.get("reason"),
                )

    n_sm = sum(
        1
        for c in mem.by_level("pdn")
        if (c.attr or {}).get("via") == "active_f4_static_mesh" and c.status == "ok"
    )
    steer_sm = steer_from_static_mesh_residual(mem)
    pay_sm, why_sm = should_pay_static_mesh(
        mem, budget_left=t_end - time.time(), steer=steer_sm, n_steer=n_sm, variant=variant
    )
    step("acquire", fidelity="F4_STATIC_MESH", pay=pay_sm, why=why_sm, steer=steer_sm)
    if (
        any(s["level"] == "static_mesh" for s in plan["steps"])
        and pay_sm
        and steer_sm
        and time.time() < t_end
    ):
        spec_sm = steer_sm.get("spec") or {}
        eid_sm = str(steer_sm.get("extract_id") or "")
        hit_sm = extract_on_disk(mem, eid_sm) if eid_sm else None
        odb_sm = steer_sm.get("odb") or ((hit_sm or {}).get("odb") if hit_sm else None)
        host_s = winning_static_pdn(mem)
        if spec_sm and odb_sm:
            child = evaluate_f4_static_mesh(
                mem,
                spec_sm,
                variant=variant,
                design_id=design_id,
                parent_id=(hit_sm or {}).get("candidate").id if hit_sm else (host_s.id if host_s else None),
                odb=odb_sm,
                insts_src=(hit_sm or {}).get("insts"),
                sta=(hit_sm or {}).get("sta"),
                host=host_s,
                parent_extract_id=eid_sm,
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "active_f4_static_mesh"
                child.attr["steer"] = {k: steer_sm[k] for k in steer_sm if k != "spec"}
                if host_s and host_s.qor.static_ir_mv is not None and child.qor.static_ir_mv is not None:
                    child.attr["residual_vs_static_champ_mv"] = float(child.qor.static_ir_mv) - float(
                        host_s.qor.static_ir_mv
                    )
                    child.attr["residual_vs_static_champ"] = host_s.id
                child.attr["residual_via"] = "static_bumps_vs_static_champ"
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="active_f4_static_mesh",
                    parent=(hit_sm or {}).get("candidate").id if hit_sm else None,
                    catalog=spec_sm.get("name"),
                    extract_id=child.knobs.get("extract_id"),
                    parent_extract_id=eid_sm,
                    bump_dx=spec_sm.get("bump_dx"),
                    static_ir_mv=child.qor.static_ir_mv,
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_static_champ_mv=(child.attr or {}).get("residual_vs_static_champ_mv"),
                    gold=False,
                    status=child.status,
                    reason=steer_sm.get("reason"),
                )

    n_st = sum(
        1
        for c in mem.by_level("pdn")
        if (c.attr or {}).get("via") == "active_f4_static_straps" and c.status == "ok"
    )
    steer_st = steer_from_static_strap_residual(mem)
    pay_st, why_st = should_pay_static_straps(
        mem, budget_left=t_end - time.time(), steer=steer_st, n_steer=n_st, variant=variant
    )
    step("acquire", fidelity="F4_STATIC_STRAPS", pay=pay_st, why=why_st, steer=steer_st)
    if (
        any(s["level"] == "static_straps" for s in plan["steps"])
        and pay_st
        and steer_st
        and time.time() < t_end
    ):
        spec_st = steer_st.get("spec") or {}
        eid_st = str(steer_st.get("extract_id") or "")
        hit_st = extract_on_disk(mem, eid_st) if eid_st else None
        odb_st = steer_st.get("odb") or ((hit_st or {}).get("odb") if hit_st else None)
        host_s = winning_static_pdn(mem)
        if spec_st and odb_st:
            child = evaluate_f4_static_straps(
                mem,
                spec_st,
                variant=variant,
                design_id=design_id,
                parent_id=(hit_st or {}).get("candidate").id if hit_st else (host_s.id if host_s else None),
                odb=odb_st,
                insts_src=(hit_st or {}).get("insts"),
                sta=(hit_st or {}).get("sta"),
                host=host_s,
                parent_extract_id=eid_st,
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "active_f4_static_straps"
                child.attr["steer"] = {k: steer_st[k] for k in steer_st if k != "spec"}
                if host_s and host_s.qor.static_ir_mv is not None and child.qor.static_ir_mv is not None:
                    child.attr["residual_vs_static_champ_mv"] = float(child.qor.static_ir_mv) - float(
                        host_s.qor.static_ir_mv
                    )
                    child.attr["residual_vs_static_champ"] = host_s.id
                child.attr["residual_via"] = "static_straps_vs_static_champ"
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="active_f4_static_straps",
                    parent=(hit_st or {}).get("candidate").id if hit_st else None,
                    catalog=spec_st.get("name"),
                    extract_id=child.knobs.get("extract_id"),
                    parent_extract_id=eid_st,
                    m4_pitch=spec_st.get("m4_pitch"),
                    static_ir_mv=child.qor.static_ir_mv,
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_static_champ_mv=(child.attr or {}).get("residual_vs_static_champ_mv"),
                    gold=False,
                    status=child.status,
                    reason=steer_st.get("reason"),
                )

    n_em = sum(
        1
        for c in mem.by_level("pdn")
        if (c.attr or {}).get("via") == "active_f4_em_straps" and c.status == "ok"
    )
    steer_em = steer_from_em_width_residual(mem)
    pay_em, why_em = should_pay_em_straps(
        mem, budget_left=t_end - time.time(), steer=steer_em, n_steer=n_em, variant=variant
    )
    step("acquire", fidelity="F4_EM_STRAPS", pay=pay_em, why=why_em, steer=steer_em)
    if (
        any(s["level"] == "em_straps" for s in plan["steps"])
        and pay_em
        and steer_em
        and time.time() < t_end
    ):
        spec_em = steer_em.get("spec") or {}
        eid_em = str(steer_em.get("extract_id") or "")
        hit_em = extract_on_disk(mem, eid_em) if eid_em else None
        odb_em = steer_em.get("odb") or ((hit_em or {}).get("odb") if hit_em else None)
        host_em = strap_extract_host(mem)
        em_win = winning_em_pdn(mem)
        if spec_em and odb_em:
            child = evaluate_f4_em_straps(
                mem,
                spec_em,
                variant=variant,
                design_id=design_id,
                parent_id=host_em.id if host_em else ((hit_em or {}).get("candidate").id if hit_em else None),
                odb=odb_em,
                insts_src=(hit_em or {}).get("insts") or ((host_em.artifacts or {}).get("insts") if host_em else None),
                sta=(hit_em or {}).get("sta"),
                host=host_em,
                parent_extract_id=eid_em,
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "active_f4_em_straps"
                child.attr["steer"] = {k: steer_em[k] for k in steer_em if k != "spec"}
                if em_win and em_win.qor.em_j_a_m2 is not None and child.qor.em_j_a_m2 is not None:
                    child.attr["residual_vs_em_champ_j"] = float(child.qor.em_j_a_m2) - float(
                        em_win.qor.em_j_a_m2
                    )
                    child.attr["residual_vs_em_champ"] = em_win.id
                if host_em and host_em.qor.em_j_a_m2 is not None and child.qor.em_j_a_m2 is not None:
                    child.attr["residual_vs_strap_j"] = float(child.qor.em_j_a_m2) - float(
                        host_em.qor.em_j_a_m2
                    )
                    child.attr["residual_vs_strap"] = host_em.id
                child.attr["residual_via"] = "em_width_vs_strap_and_em_champ"
                mem.touch(child)
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="active_f4_em_straps",
                    parent=host_em.id if host_em else None,
                    catalog=spec_em.get("name"),
                    extract_id=child.knobs.get("extract_id"),
                    parent_extract_id=eid_em,
                    m4_width=spec_em.get("m4_width"),
                    m4_pitch=spec_em.get("m4_pitch"),
                    em_j_a_m2=child.qor.em_j_a_m2,
                    static_ir_mv=child.qor.static_ir_mv,
                    droop_mv=child.qor.dynamic_ir_mv,
                    residual_vs_em_champ_j=(child.attr or {}).get("residual_vs_em_champ_j"),
                    residual_vs_strap_j=(child.attr or {}).get("residual_vs_strap_j"),
                    gold=False,
                    status=child.status,
                    reason=steer_em.get("reason"),
                )

    return True

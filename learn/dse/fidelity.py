"""Fidelity adapters. F4 is the existing Dynamic IR engine — ingest, don't fake.

F0  cheap analytical / SSK-GP / RUDY-class proxy
F1  Yosys + ABC liberty map + equiv (logic or architecture RTL)
F2  ingest OpenROAD place / GRT, F2-fast netgraph, budgeted OpenROAD GPL
F3  OpenSTA on the *candidate* (ideal or GRT SDF) + ingest of signoff STA
F4  Dynamic IR / EM ingest (Solver A gold stays 45.298 mV on the GCD)
F5  budgeted detailed_route + OpenRCX SPEF (F5-lite ideal clock, or paid F5-CTS)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from .abc_space import write_abc_script
from .arch_space import is_cone_abc
from .designs import design_rtl, resolve, rtl_inputs
from .fingerprint import knobs_fp, sha256_file, sha256_text
from .frame import (
    _suffix as _refine_suffix,
    refine_cell_source,
    refine_depth,
    refine_extract_source,
    refine_label,
)
from .memory import Candidate, DesignMemory
from .metrics import QoR, core_util_from_report, enrich_parent_qor_from, inherit_parent_pd, merge_sta_into_qor, wns_cost_from_slack_ns
from .netgraph import (
    estimate_physical,
    is_gate_cell_netlist,
    parse_mapped_verilog,
    features as net_features,
)
from .openroad_f2 import (
    evaluate_f5_cts as run_f5_cts,
    evaluate_f5_drt as run_f5_drt,
    evaluate_gpl,
    evaluate_grt,
)
from .sta_f3 import evaluate_sta, export_arrivals

REPO = Path(__file__).resolve().parents[1].parent
NANGATE_LIB = (
    REPO
    / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
)
ORFS = REPO / "tools/OpenROAD-flow-scripts/flow"


def _refine_prior_extract(mem: DesignMemory, depth: int):
    """Residual target for a depth-N refine extract: depth N−1 mesh (region at 0)."""
    src = "f4_winning_ir_region_extract" if depth <= 0 else refine_extract_source(depth - 1)
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == src:
            return c
    return None


def _residual_mv(ext: dict, prior) -> float | None:
    """Prefer SolveResult.abs_err_vs_reference_mv; else signed child−prior droop."""
    from .solve_result import residual_vs_reference_mv

    prior_mv = None if prior is None or prior.qor.dynamic_ir_mv is None else float(prior.qor.dynamic_ir_mv)
    return residual_vs_reference_mv(
        ext,
        fallback_child_mv=ext.get("worst_droop_mv"),
        fallback_ref_mv=prior_mv,
    )


def _stamp_f4_attr(attr: dict, payload: dict | None) -> dict:
    from .solve_result import stamp_activity_on_attr

    return stamp_activity_on_attr(attr, payload)


COST_HINT = {
    "F0": 0.05,
    "F1": 2.0,
    "F2": 30.0,
    "F2_FAST": 0.2,
    "F2_GPL": 8.0,
    "F2_GRT": 8.0,
    "F3": 2.0,
    "F3_SDF": 2.0,
    "F4": 12.0,
    "F4_EXTRACT": 15.0,
    "F5": 15.0,
    "F5_CTS": 25.0,
}


def _overlay_sta(raw: dict, sta: dict) -> dict:
    """Copy OpenSTA WNS/TNS/power split onto an F5/GRT blob. Missing stays missing."""
    out = dict(raw)
    out["sta"] = sta
    for k in (
        "wns_ns",
        "tns_ns",
        "power_w",
        "leakage_w",
        "internal_power_w",
        "switching_power_w",
    ):
        if sta.get(k) is not None:
            out[k] = sta[k]
    if sta.get("interconnect"):
        out["interconnect"] = sta.get("interconnect")
    return out


def reports_dir(variant: str) -> Path:
    return REPO / "learn" / "sim" / "reports"


def dynamic_ir_current_path(variant: str) -> Path:
    """Prefer current_run I(t). Gold 45.298 mV stays dynamic_ir_flowlab.json."""
    rd = reports_dir(variant)
    direct = rd / f"dynamic_ir_{variant}_direct.json"
    if direct.is_file():
        return direct
    return rd / f"dynamic_ir_{variant}.json"


def orfs_logs(variant: str) -> Path:
    return ORFS / "logs" / "nangate45" / "gcd" / variant


def orfs_results(variant: str, design_id: str = "gcd") -> Path:
    from .designs import resolve

    spec = resolve(design_id)
    return ORFS / "results" / spec.platform / spec.orfs_design / variant


def flowlab_params(root: Path | None = None) -> dict:
    p = (root or REPO) / "learn" / "flowlab" / "params.json"
    if not p.is_file():
        return {}
    return json.loads(p.read_text())


def ingest_physical(variant: str, mem: DesignMemory, design_id: str = "gcd") -> Candidate | None:
    """F3+F4 observation of the *current* layout. Separate level from ABC search."""
    rd = reports_dir(variant)
    sta = _read_json(rd / f"sta_signoff_{variant}.json")
    ir = _read_json(dynamic_ir_current_path(variant))
    chip = _read_json(rd / f"pdn_chip_ir_{variant}.json")
    if not ir and not sta:
        return None
    params = flowlab_params()
    knobs = {
        "coreUtilization": params.get("coreUtilization"),
        "placeDensityAddon": params.get("placeDensityAddon"),
        "abcArea": params.get("abcArea"),
        "sdcPreset": params.get("sdcPreset"),
        "tnsEndPercent": params.get("tnsEndPercent"),
        "source": "ingest_layout",
    }
    fp = knobs_fp("physical", knobs)
    if fp in mem.seen_knobs("physical"):
        return next(c for c in mem.by_level("physical") if c.knobs_fp == fp)
    dyn = (ir or {}).get("dynamic") or {}
    static = (ir or {}).get("static") or (chip or {}).get("static") or {}
    em = (ir or {}).get("em") or {}
    slack = None
    timing = (ir or {}).get("timing_impact") or {}
    path = (timing.get("path") or {}) if isinstance(timing, dict) else {}
    if path.get("slack_ns") is not None:
        slack = float(path["slack_ns"])
    elif sta and (sta.get("timing") or {}).get("wns_ns") is not None:
        slack = float(sta["timing"]["wns_ns"])
    yosys_v = orfs_results(variant) / "1_2_yosys.v"
    q = QoR(
        wns_cost=wns_cost_from_slack_ns(slack),
        static_ir_mv=_mv(static.get("worst_ir"), static.get("worst_ir_mv")),
        dynamic_ir_mv=_mv(
            dyn.get("worst_droop"),
            dyn.get("worst_droop_mv")
            if dyn.get("worst_droop_mv") is not None
            else (ir or {}).get("worst_droop_mv") if (ir or {}).get("gold") is True else None,
        ),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        fidelity="F4" if ir else "F3",
        note=(
            "ingested gold teacher — not current_run I(t)"
            if (ir or {}).get("gold") is True
            else "ingested layout oracles — current_run I(t), not gold 45.298"
        ),
    )
    rtl = design_rtl(design_id)
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=None,
        level="physical",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(rtl),
        netlist_fp=sha256_file(yosys_v) if yosys_v.is_file() else None,
        fidelity=q.fidelity,
        qor=q,
        cost_s=0.0,
        note="F3/F4 ingest of existing FlowLab finish + Dynamic IR",
    )
    return mem.add(c)


def ingest_pdn(variant: str, mem: DesignMemory, design_id: str = "gcd") -> Candidate | None:
    ir = _read_json(dynamic_ir_current_path(variant))
    if not ir:
        return None
    dyn = ir.get("dynamic") or {}
    knobs = {
        "pkg_r": dyn.get("pkg_r"),
        "pkg_l": dyn.get("pkg_l"),
        "c_decap": dyn.get("c_decap"),
        "mode": ir.get("mode"),
        "source": "ingest_pdn",
    }
    fp = knobs_fp("pdn", knobs)
    if fp in mem.seen_knobs("pdn"):
        return next(c for c in mem.by_level("pdn") if c.knobs_fp == fp)
    em = ir.get("em") or {}
    static = ir.get("static") or {}
    q = QoR(
        static_ir_mv=_mv(static.get("worst_ir"), static.get("worst_ir_mv")),
        dynamic_ir_mv=_mv(
            dyn.get("worst_droop"),
            dyn.get("worst_droop_mv")
            if dyn.get("worst_droop_mv") is not None
            else ir.get("worst_droop_mv") if ir.get("gold") is True else None,
        ),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        fidelity="F4",
        note=(
            "PDN-level gold teacher — not current_run I(t)"
            if ir.get("gold") is True
            else "PDN-level observation on current_run I(t); gold 45.298 is another extract"
        ),
    )
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=None,
        level="pdn",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(design_rtl(design_id)),
        netlist_fp=None,
        fidelity="F4",
        qor=q,
        cost_s=0.0,
        note="F4 PDN ingest — does not re-run TRAN",
    )
    return mem.add(c)


def evaluate_f4_pdn(
    mem: DesignMemory,
    spec: dict,
    *,
    variant: str = "flowlab",
    design_id: str = "gcd",
    parent_id: str | None = None,
    spice: Path | str | None = None,
    insts: Path | str | None = None,
    extract_id: str = "finish",
    solver: str = "direct",
    sta: Path | str | None = None,
    timeout_s: float | None = None,
) -> Candidate | None:
    """PDN-level restamp. Different c_decap/pkg L / solver; named extract. Not gold."""
    from .attribute import attribute_dynamic_ir, ir_report_from_solve
    from .f4_oracle import solve_f4

    knobs = {
        "name": spec.get("name"),
        "pkg_r": spec["pkg_r"],
        "pkg_l": spec["pkg_l"],
        "c_decap": spec["c_decap"],
        "i_scale": 1.0,
        "solver": solver,
        "source": "f4_solver_a" if solver == "direct" else f"f4_solver_{solver}",
        "extract_id": extract_id,
    }
    fp = knobs_fp("pdn", knobs)
    if fp in mem.seen_knobs("pdn"):
        return next(c for c in mem.by_level("pdn") if c.knobs_fp == fp)
    dyn_kw: dict = dict(
        variant=variant,
        pkg_r=float(spec["pkg_r"]),
        pkg_l=float(spec["pkg_l"]),
        c_decap=float(spec["c_decap"]),
        i_scale=1.0,
        spice=spice,
        insts=insts,
        extract_kind="candidate" if spice else "finish",
        solver=solver,
        sta=sta,
    )
    if timeout_s is not None:
        dyn_kw["timeout_s"] = float(timeout_s)
    n_r = None
    from .acquire import extract_on_disk
    from .f4_oracle import n_r_from_spice

    hit = extract_on_disk(mem, str(extract_id)) if extract_id else None
    if hit and hit.get("n_r") is not None:
        n_r = int(hit["n_r"])
    if n_r is None:
        n_r = n_r_from_spice(spice)
    dyn_kw["n_r"] = n_r
    dyn = solve_f4(**dyn_kw)
    em = dyn.get("em") or {}
    attr = attribute_dynamic_ir(ir_report_from_solve(dyn, insts=insts))
    attr = _stamp_f4_attr(attr, dyn)
    q = QoR(
        static_ir_mv=dyn.get("static_ir_mv"),
        dynamic_ir_mv=dyn.get("worst_droop_mv"),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        fidelity="F4",
        note=dyn.get("note") or "Solver A restamp — not gold",
    )
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=parent_id,
        level="pdn",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(design_rtl(design_id)),
        netlist_fp=None,
        fidelity="F4",
        qor=q,
        cost_s=float(dyn.get("cost_s") or 0.0),
        artifacts=dyn,
        attr=attr,
        status="ok" if dyn.get("status") == "ok" else "fail",
        failure=dyn.get("reason") if dyn.get("status") != "ok" else None,
        note=f"F4 PDN {spec.get('name')} on {extract_id} droop={dyn.get('worst_droop_mv')} — not gold",
    )
    return mem.add(c)


def evaluate_f4_static_mesh(
    mem: DesignMemory,
    spec: dict,
    *,
    variant: str = "flowlab",
    design_id: str = "gcd",
    parent_id: str | None = None,
    odb: Path | str,
    insts_src: Path | str | None = None,
    sta: Path | str | None = None,
    host=None,
    parent_extract_id: str = "",
) -> Candidate | None:
    """Denser bump write_pg_spice on an existing ODB. Not a new GPL, not gold."""
    from .attribute import attribute_dynamic_ir, ir_report_from_solve
    from .f4_oracle import solve_f4
    from .openroad_f2 import extract_pdn_bumps

    knobs = {
        "source": "f4_static_mesh_extract",
        "name": spec.get("name"),
        "bump_dx": float(spec["bump_dx"]),
        "bump_dy": float(spec["bump_dy"]),
        "bump_size": float(spec.get("bump_size") or 40.0),
        "bump_interval": int(spec.get("bump_interval") or 3),
        "pkg_r": float((host.knobs or {}).get("pkg_r") or 0.05) if host else 0.05,
        "pkg_l": float((host.knobs or {}).get("pkg_l") or 2e-10) if host else 2e-10,
        "c_decap": float((host.knobs or {}).get("c_decap") or 50e-15) if host else 50e-15,
        "i_scale": 1.0,
        "parent_extract_id": parent_extract_id,
        "parent_id": parent_id,
        "script": "write_pg_spice_bumps",
    }
    fp = knobs_fp("pdn", knobs)
    if fp in mem.seen_knobs("pdn"):
        hit = next(c for c in mem.by_level("pdn") if c.knobs_fp == fp)
        if hit.status == "ok":
            return hit
    cid = DesignMemory.new_id()
    out_dir = REPO / "learn" / "sim" / "dse" / "extracts" / cid
    ext = extract_pdn_bumps(
        Path(odb),
        out_dir,
        bump_dx=float(spec["bump_dx"]),
        bump_dy=float(spec["bump_dy"]),
        bump_size=float(spec.get("bump_size") or 40.0),
        bump_interval=int(spec.get("bump_interval") or 3),
        pkg_r=float(knobs["pkg_r"]),
        insts_src=insts_src,
    )
    spice, insts = ext.get("spice"), ext.get("insts")
    dyn: dict = {}
    extract_cost = float(ext.get("cost_s") or 0.0)
    if ext.get("status") == "ok" and spice and insts:
        sta_p = Path(sta) if sta and Path(sta).is_file() else None
        dyn = solve_f4(
            variant=variant,
            pkg_r=float(knobs["pkg_r"]),
            pkg_l=float(knobs["pkg_l"]),
            c_decap=float(knobs["c_decap"]),
            i_scale=1.0,
            spice=spice,
            insts=insts,
            extract_kind="candidate",
            sta=sta_p,
        )
        ext = {**ext, **{k: v for k, v in dyn.items() if k != "cost_s"}}
        ext["extract_cost_s"] = extract_cost
        ext["solve_cost_s"] = dyn.get("cost_s")
        ext["cost_s"] = extract_cost + float(dyn.get("cost_s") or 0.0)
    knobs["extract_id"] = cid
    em = (dyn.get("em") or ext.get("em") or {}) if isinstance(dyn, dict) else {}
    attr = attribute_dynamic_ir(ir_report_from_solve({**ext, **(dyn or {})}, insts=insts))
    attr["via"] = "active_f4_static_mesh"
    attr["extract_id"] = cid
    attr["parent_extract_id"] = parent_extract_id
    attr = _stamp_f4_attr(attr, ext if ext else dyn)
    q = QoR(
        static_ir_mv=ext.get("static_ir_mv") or dyn.get("static_ir_mv"),
        dynamic_ir_mv=ext.get("worst_droop_mv") or dyn.get("worst_droop_mv"),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        fidelity="F4",
        note=(
            f"static-IR bump mesh {spec.get('name')} n_v={ext.get('n_v')} "
            f"static={ext.get('static_ir_mv')} — not finish, not gold"
        ),
    )
    ok = ext.get("status") == "ok" and (not dyn or dyn.get("status") == "ok")
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent_id,
        level="pdn",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(design_rtl(design_id)),
        netlist_fp=None,
        fidelity="F4",
        qor=q,
        cost_s=float(ext.get("cost_s") or 0.0),
        artifacts=ext,
        attr=attr,
        status="ok" if ok else "fail",
        failure=ext.get("reason") if not ok else None,
        note=f"F4 static mesh {spec.get('name')} on {parent_extract_id} — not gold",
    )
    return mem.add(c)


def evaluate_f4_static_straps(
    mem: DesignMemory,
    spec: dict,
    *,
    variant: str = "flowlab",
    design_id: str = "gcd",
    parent_id: str | None = None,
    odb: Path | str,
    insts_src: Path | str | None = None,
    sta: Path | str | None = None,
    host=None,
    parent_extract_id: str = "",
) -> Candidate | None:
    """Denser metal4 pdngen on an existing ODB. Not a new GPL, not bumps, not gold."""
    from .attribute import attribute_dynamic_ir, ir_report_from_solve
    from .f4_oracle import solve_f4
    from .openroad_f2 import extract_pdn_straps

    knobs = {
        "source": "f4_static_strap_extract",
        "name": spec.get("name"),
        "m4_pitch": float(spec["m4_pitch"]),
        "m4_width": float(spec.get("m4_width") or 0.48),
        "m7_pitch": float(spec.get("m7_pitch") or 30.0),
        "m7_width": float(spec.get("m7_width") or 1.40),
        "pkg_r": float((host.knobs or {}).get("pkg_r") or 0.05) if host else 0.05,
        "pkg_l": float((host.knobs or {}).get("pkg_l") or 2e-10) if host else 2e-10,
        "c_decap": float((host.knobs or {}).get("c_decap") or 50e-15) if host else 50e-15,
        "i_scale": 1.0,
        "parent_extract_id": parent_extract_id,
        "parent_id": parent_id,
        "script": "write_pg_spice_straps",
    }
    fp = knobs_fp("pdn", knobs)
    if fp in mem.seen_knobs("pdn"):
        hit = next(c for c in mem.by_level("pdn") if c.knobs_fp == fp)
        if hit.status == "ok":
            return hit
    cid = DesignMemory.new_id()
    out_dir = REPO / "learn" / "sim" / "dse" / "extracts" / cid
    ext = extract_pdn_straps(
        Path(odb),
        out_dir,
        m4_pitch=float(spec["m4_pitch"]),
        m4_width=float(spec.get("m4_width") or 0.48),
        m7_pitch=float(spec.get("m7_pitch") or 30.0),
        m7_width=float(spec.get("m7_width") or 1.40),
        pkg_r=float(knobs["pkg_r"]),
        insts_src=insts_src,
    )
    spice, insts = ext.get("spice"), ext.get("insts")
    dyn: dict = {}
    extract_cost = float(ext.get("cost_s") or 0.0)
    if ext.get("status") == "ok" and spice and insts:
        sta_p = Path(sta) if sta and Path(sta).is_file() else None
        dyn = solve_f4(
            variant=variant,
            pkg_r=float(knobs["pkg_r"]),
            pkg_l=float(knobs["pkg_l"]),
            c_decap=float(knobs["c_decap"]),
            i_scale=1.0,
            spice=spice,
            insts=insts,
            extract_kind="candidate",
            sta=sta_p,
        )
        ext = {**ext, **{k: v for k, v in dyn.items() if k != "cost_s"}}
        ext["extract_cost_s"] = extract_cost
        ext["solve_cost_s"] = dyn.get("cost_s")
        ext["cost_s"] = extract_cost + float(dyn.get("cost_s") or 0.0)
    knobs["extract_id"] = cid
    em = (dyn.get("em") or ext.get("em") or {}) if isinstance(dyn, dict) else {}
    attr = attribute_dynamic_ir(ir_report_from_solve({**ext, **(dyn or {})}, insts=insts))
    attr["via"] = "active_f4_static_straps"
    attr["extract_id"] = cid
    attr["parent_extract_id"] = parent_extract_id
    attr = _stamp_f4_attr(attr, ext if ext else dyn)
    q = QoR(
        static_ir_mv=ext.get("static_ir_mv") or dyn.get("static_ir_mv"),
        dynamic_ir_mv=ext.get("worst_droop_mv") or dyn.get("worst_droop_mv"),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        fidelity="F4",
        note=(
            f"static-IR metal4 straps {spec.get('name')} n_r={ext.get('n_r')} "
            f"static={ext.get('static_ir_mv')} — not finish, not gold"
        ),
    )
    ok = ext.get("status") == "ok" and (not dyn or dyn.get("status") == "ok")
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent_id,
        level="pdn",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(design_rtl(design_id)),
        netlist_fp=None,
        fidelity="F4",
        qor=q,
        cost_s=float(ext.get("cost_s") or 0.0),
        artifacts=ext,
        attr=attr,
        status="ok" if ok else "fail",
        failure=ext.get("reason") if not ok else None,
        note=f"F4 static straps {spec.get('name')} on {parent_extract_id} — not gold",
    )
    return mem.add(c)


def evaluate_f4_em_straps(
    mem: DesignMemory,
    spec: dict,
    *,
    variant: str = "flowlab",
    design_id: str = "gcd",
    parent_id: str | None = None,
    odb: Path | str,
    insts_src: Path | str | None = None,
    sta: Path | str | None = None,
    host=None,
    parent_extract_id: str = "",
) -> Candidate | None:
    """Wider metal4 pdngen on the strap-pitch geometry. Not a new GPL, not pitch, not gold."""
    from .attribute import attribute_dynamic_ir, ir_report_from_solve
    from .f4_oracle import solve_f4
    from .openroad_f2 import extract_pdn_straps

    knobs = {
        "source": "f4_em_strap_extract",
        "name": spec.get("name"),
        "m4_pitch": float(spec["m4_pitch"]),
        "m4_width": float(spec["m4_width"]),
        "m7_pitch": float(spec.get("m7_pitch") or 30.0),
        "m7_width": float(spec.get("m7_width") or 1.40),
        "pkg_r": float((host.knobs or {}).get("pkg_r") or 0.05) if host else 0.05,
        "pkg_l": float((host.knobs or {}).get("pkg_l") or 2e-10) if host else 2e-10,
        "c_decap": float((host.knobs or {}).get("c_decap") or 50e-15) if host else 50e-15,
        "i_scale": 1.0,
        "parent_extract_id": parent_extract_id,
        "parent_id": parent_id,
        "script": "write_pg_spice_em_straps",
    }
    fp = knobs_fp("pdn", knobs)
    if fp in mem.seen_knobs("pdn"):
        hit = next(c for c in mem.by_level("pdn") if c.knobs_fp == fp)
        if hit.status == "ok":
            return hit
    cid = DesignMemory.new_id()
    out_dir = REPO / "learn" / "sim" / "dse" / "extracts" / cid
    ext = extract_pdn_straps(
        Path(odb),
        out_dir,
        m4_pitch=float(spec["m4_pitch"]),
        m4_width=float(spec["m4_width"]),
        m7_pitch=float(spec.get("m7_pitch") or 30.0),
        m7_width=float(spec.get("m7_width") or 1.40),
        pkg_r=float(knobs["pkg_r"]),
        insts_src=insts_src,
    )
    spice, insts = ext.get("spice"), ext.get("insts")
    dyn: dict = {}
    extract_cost = float(ext.get("cost_s") or 0.0)
    if ext.get("status") == "ok" and spice and insts:
        sta_p = Path(sta) if sta and Path(sta).is_file() else None
        dyn = solve_f4(
            variant=variant,
            pkg_r=float(knobs["pkg_r"]),
            pkg_l=float(knobs["pkg_l"]),
            c_decap=float(knobs["c_decap"]),
            i_scale=1.0,
            spice=spice,
            insts=insts,
            extract_kind="candidate",
            sta=sta_p,
        )
        ext = {**ext, **{k: v for k, v in dyn.items() if k != "cost_s"}}
        ext["extract_cost_s"] = extract_cost
        ext["solve_cost_s"] = dyn.get("cost_s")
        ext["cost_s"] = extract_cost + float(dyn.get("cost_s") or 0.0)
    knobs["extract_id"] = cid
    em = (dyn.get("em") or ext.get("em") or {}) if isinstance(dyn, dict) else {}
    attr = attribute_dynamic_ir(ir_report_from_solve({**ext, **(dyn or {})}, insts=insts))
    attr["via"] = "active_f4_em_straps"
    attr["extract_id"] = cid
    attr["parent_extract_id"] = parent_extract_id
    attr = _stamp_f4_attr(attr, ext if ext else dyn)
    q = QoR(
        static_ir_mv=ext.get("static_ir_mv") or dyn.get("static_ir_mv"),
        dynamic_ir_mv=ext.get("worst_droop_mv") or dyn.get("worst_droop_mv"),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        fidelity="F4",
        note=(
            f"EM metal4 width {spec.get('name')} n_r={ext.get('n_r')} "
            f"J={em.get('j_absmax_a_m2')} — not finish, not gold"
        ),
    )
    ok = ext.get("status") == "ok" and (not dyn or dyn.get("status") == "ok")
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent_id,
        level="pdn",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(design_rtl(design_id)),
        netlist_fp=None,
        fidelity="F4",
        qor=q,
        cost_s=float(ext.get("cost_s") or 0.0),
        artifacts=ext,
        attr=attr,
        status="ok" if ok else "fail",
        failure=ext.get("reason") if not ok else None,
        note=f"F4 EM straps {spec.get('name')} on {parent_extract_id} — not gold",
    )
    return mem.add(c)


def evaluate_f4_scale(
    parent: Candidate,
    mem: DesignMemory,
    *,
    variant: str = "flowlab",
    design_id: str = "gcd",
    baseline_power_w: float,
    pkg_r: float = 0.05,
    pkg_l: float = 2e-10,
    c_decap: float = 50e-15,
    spice: Path | str | None = None,
    insts: Path | str | None = None,
    extract_id: str = "finish",
    sta: Path | str | None = None,
    sta_via: str | None = None,
    source: str = "f4_iscale",
) -> Candidate | None:
    """Named extract + PDN knobs; I(t) × (attributed host F3 power / baseline).

    Host is the hierarchical incumbent (port-steer / port-net / net / cell)
    when present — not a silent flatten to the synth WNS-winner. Not a VCD map.
    source=f4_iscale_win restamps the winning host PDN point after host IR-steer.
    source=f4_iscale_champ restamps winning_ir_pdn (IR-cell family) — not host-win.
    """
    from .attribute import attribute_dynamic_ir, ir_report_from_solve, persist_hotspot_join
    from .f4_oracle import solve_f4
    from .mo import timing_of

    _wns, pwr = timing_of(mem, parent)
    if pwr is None or baseline_power_w <= 0:
        return None
    scale = float(pwr) / float(baseline_power_w)
    host = parent.knobs.get("name") or parent.knobs.get("source") or parent.level
    knobs = {
        "name": f"iscale_{host}",
        "pkg_r": pkg_r,
        "pkg_l": pkg_l,
        "c_decap": c_decap,
        "i_scale": scale,
        "parent_id": parent.id,
        "parent_name": host,
        "host_level": parent.level,
        "host_source": parent.knobs.get("source") or parent.level,
        "source": source,
        "extract_id": extract_id,
        "sta_via": sta_via or ("extract" if sta else "none"),
    }
    if source == "f4_iscale_win":
        knobs["name"] = f"iscale_win_{host}"
    if source == "f4_iscale_champ":
        knobs["name"] = f"iscale_champ_{host}"
    fp = knobs_fp("pdn", knobs)
    if fp in mem.seen_knobs("pdn"):
        return next(c for c in mem.by_level("pdn") if c.knobs_fp == fp)
    from .acquire import extract_on_disk
    from .f4_oracle import n_r_from_spice

    n_r = None
    hit = extract_on_disk(mem, str(extract_id)) if extract_id else None
    if hit and hit.get("n_r") is not None:
        n_r = int(hit["n_r"])
    if n_r is None:
        n_r = n_r_from_spice(spice)
    dyn = solve_f4(
        variant=variant,
        pkg_r=pkg_r,
        pkg_l=pkg_l,
        c_decap=c_decap,
        i_scale=scale,
        spice=spice,
        insts=insts,
        extract_kind="candidate" if spice else "finish",
        sta=sta,
        n_r=n_r,
    )
    em = dyn.get("em") or {}
    attr = attribute_dynamic_ir(ir_report_from_solve(dyn, insts=insts))
    attr["transform"] = host
    attr["i_scale"] = scale
    attr["inherited_from"] = parent.id
    attr["extract_id"] = extract_id
    attr["host_level"] = parent.level
    attr["host_source"] = parent.knobs.get("source") or parent.level
    attr["sta_via"] = sta_via or ("extract" if sta else "none")
    q = QoR(
        static_ir_mv=dyn.get("static_ir_mv"),
        dynamic_ir_mv=dyn.get("worst_droop_mv"),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        power_w=pwr,
        fidelity="F4",
        note=f"I(t)×{scale:.3f} on {extract_id} — not gold, not a new VCD map",
    )
    inherit_parent_pd(q, parent.qor)
    if source == "f4_iscale_win":
        attr["via"] = "f4_iscale_win"
    if source == "f4_iscale_champ":
        attr["via"] = "f4_iscale_champ"
    attr = _stamp_f4_attr(attr, dyn)
    if dyn.get("status") == "ok" and dyn.get("worst_droop_mv") is not None and source == "f4_iscale":
        parent.qor.dynamic_ir_mv = float(dyn["worst_droop_mv"])
        if dyn.get("static_ir_mv") is not None:
            parent.qor.static_ir_mv = float(dyn["static_ir_mv"])
        if em.get("j_absmax_a_m2") is not None:
            parent.qor.em_j_a_m2 = float(em["j_absmax_a_m2"])
        parent.attr = dict(parent.attr or {})
        parent.attr["f4_iscale"] = {
            "i_scale": scale,
            "droop_mv": dyn["worst_droop_mv"],
            "static_ir_mv": dyn.get("static_ir_mv"),
            "extract_id": extract_id,
            "em_j_a_m2": em.get("j_absmax_a_m2"),
            "sta_via": sta_via or ("extract" if sta else "none"),
        }
        mem.touch(parent)
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=parent.id,
        level="pdn",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F4",
        qor=q,
        cost_s=float(dyn.get("cost_s") or 0.0),
        artifacts=dyn,
        attr=attr,
        status="ok" if dyn.get("status") == "ok" else "fail",
        failure=dyn.get("reason") if dyn.get("status") != "ok" else None,
        note=f"F4 I-scale of {host} ×{scale:.3f} on {extract_id} droop={dyn.get('worst_droop_mv')}",
    )
    added = mem.add(c)
    if source == "f4_iscale_champ" and persist_hotspot_join(added):
        mem.touch(added)
    return added


def evaluate_host_arrivals(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
) -> Candidate | None:
    """OpenSTA report_arrival on the attributed host netlist.

    t50 teacher for I(t) — name-join onto the named extract. Not a VCD→ITerm
    map and not the synth extract's arrivals.
    """
    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    host = parent.knobs.get("name") or parent.knobs.get("source") or parent.level
    knobs = {
        "name": f"arrivals_{host}",
        "source": "f4_host_arrivals",
        "parent_id": parent.id,
        "parent_name": host,
        "host_level": parent.level,
        "host_source": parent.knobs.get("source") or parent.level,
    }
    fp = knobs_fp("pdn", knobs)
    if fp in mem.seen_knobs("pdn"):
        return next(c for c in mem.by_level("pdn") if c.knobs_fp == fp)
    cid = DesignMemory.new_id()
    dest = REPO / "learn" / "sim" / "dse" / "arrivals" / cid / "sta_arrivals.json"
    arr = export_arrivals(Path(mapped), dest, design_id=design_id)
    n_inst = int(arr.get("n_inst") or 0)
    # Hierarchical hosts used to report only top-level portbufs (n=2).
    # Leaf coverage is required — two port pins are not a t50 teacher.
    sta_p = dest if dest.is_file() and arr.get("status") == "ok" and n_inst >= 8 else None
    if dest.is_file() and n_inst < 8:
        arr = dict(arr)
        arr["status"] = "fail"
        arr["reason"] = f"host arrivals n_inst={n_inst} is top-level-only, not a t50 teacher"
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=parent.qor.n_cells,
        fidelity="F3",
        note=(
            f"report_arrival on {host} n_inst={arr.get('n_inst')} "
            "— attributed host t50, not extract STA, not VCD"
        ),
    )
    inherit_parent_pd(q, parent.qor)
    return mem.add(
        Candidate(
            id=cid,
            design_id=design_id,
            parent_id=parent.id,
            level="pdn",
            knobs=knobs,
            knobs_fp=fp,
            rtl_fp=parent.rtl_fp,
            netlist_fp=parent.netlist_fp,
            fidelity="F3",
            qor=q,
            cost_s=float(arr.get("cost_s") or 0.0),
            artifacts={
                **arr,
                "sta_arrivals": str(sta_p) if sta_p else None,
                "mapped_v": mapped,
                "n_inst": arr.get("n_inst"),
            },
            attr={
                "via": "f4_host_arrivals",
                "host_level": parent.level,
                "host_source": parent.knobs.get("source") or parent.level,
                "inherited_from": parent.id,
                "n_inst": arr.get("n_inst"),
                "not": "a VCD→ITerm map or the synth extract arrivals",
            },
            status="ok" if arr.get("status") == "ok" and sta_p else "fail",
            failure=arr.get("reason") if arr.get("status") != "ok" else None,
            note=f"F3 arrivals of {host} n_inst={arr.get('n_inst')} — not extract STA",
        )
    )


def evaluate_f4_extract(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    variant: str = "flowlab",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 60.0,
    pkg_r: float = 0.05,
    pkg_l: float = 2e-10,
    c_decap: float = 50e-15,
    x_dbu: float | None = None,
    y_dbu: float | None = None,
    region: str | None = None,
    region_density: float | None = None,
    kind: str = "candidate",
    sta: Path | str | None = None,
) -> Candidate | None:
    """New write_pg_spice after legalized place, then Solver A. Not finish, not gold.

    kind=host extracts the attributed hierarchical netlist (port-steer/…).
    That mesh is not the synth F1 extract and not gold.
    kind=host_region density-caps the host IR bin (not gold rXY on synth F1).
    kind=ir_cell extracts the IR-hotspot sized netlist and residuals vs host extract.
    kind=ir_cell_region density-caps the IR-cell 1× bin (not host rXY, not gold rXY).
    kind=ir_cell_champ extracts the I-scale-champ dpath-sized netlist and residuals vs IR-cell extract.
    kind=ir_cell_champ_cone extracts leftover-cone size-up and residuals vs the IR-cell-champ extract.
    kind=ir_cell_champ_cone_region density-caps the leftover-cone 1× bin (not IR-cell-region rXY, not gold rXY).
    kind=winning_ir_region density-caps the winning-IR 1× bin (not leftover-cone rXY, not IR-cell-region rXY, not gold rXY); re-pays when the residual hotspot leaves the capped bin.
    kind=winning_ir_region_cell extracts leftover combo size-up on the IR-cell netlist (not leftover-cone) and residuals vs the winning-IR-region extract.
    kind=winning_ir_region_cell_leftover extracts leftover leftover size-up on the leftover-combo netlist (not leftover-combo flatten) and residuals vs the leftover-combo extract.
    kind=winning_ir_region_cell_leftover2 extracts leftover leftover leftover size-up on the leftover leftover netlist (not leftover leftover flatten) and residuals vs the leftover leftover extract.
    """
    from .attribute import attribute_dynamic_ir, ir_report_from_solve, persist_hotspot_join
    from .f4_oracle import solve_f4
    from .openroad_f2 import extract_pdn

    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    host = parent.knobs.get("name") or parent.knobs.get("source") or parent.level
    knobs = {
        "source": "f4_candidate_extract",
        "parent_id": parent.id,
        "parent_name": host,
        "util": util,
        "density": density,
        "legalize": "detailed_placement",
        "pkg_r": pkg_r,
        "pkg_l": pkg_l,
        "c_decap": c_decap,
        "i_scale": 1.0,
        "name": f"extract_{host}",
    }
    if kind == "host":
        knobs["source"] = "f4_host_extract"
        knobs["name"] = f"extract_host_{host}"
        knobs["host_level"] = parent.level
        knobs["host_source"] = parent.knobs.get("source") or parent.level
    elif kind == "host_region":
        knobs["source"] = "f4_host_region_extract"
        knobs["name"] = f"extract_host_region_{host}"
        knobs["host_level"] = parent.level
        knobs["host_source"] = parent.knobs.get("source") or parent.level
        knobs["region"] = region
        knobs["x_dbu"] = x_dbu
        knobs["y_dbu"] = y_dbu
        knobs["region_density"] = region_density if region_density is not None else 0.30
    elif kind == "ir_cell":
        knobs["source"] = "f4_ir_cell_extract"
        knobs["name"] = f"extract_ir_cell_{host}"
        knobs["host_level"] = parent.level
        knobs["host_source"] = parent.knobs.get("source") or parent.level
        knobs["ir_join"] = 1
    elif kind == "ir_cell_region":
        knobs["source"] = "f4_ir_cell_region_extract"
        knobs["name"] = f"extract_ir_cell_region_{host}"
        knobs["host_level"] = parent.level
        knobs["host_source"] = parent.knobs.get("source") or parent.level
        knobs["ir_join"] = 1
        knobs["region"] = region
        knobs["x_dbu"] = x_dbu
        knobs["y_dbu"] = y_dbu
        knobs["region_density"] = region_density if region_density is not None else 0.30
    elif kind == "ir_cell_champ":
        knobs["source"] = "f4_ir_cell_champ_extract"
        knobs["name"] = f"extract_ir_cell_champ_{host}"
        knobs["host_level"] = parent.level
        knobs["host_source"] = parent.knobs.get("source") or parent.level
        knobs["ir_join"] = 1
        knobs["champ"] = 1
        knobs["parent_extract_id"] = str((parent.knobs or {}).get("extract_id") or "")
    elif kind == "ir_cell_champ_cone":
        knobs["source"] = "f4_ir_cell_champ_cone_extract"
        knobs["name"] = f"extract_ir_cell_champ_cone_{host}"
        knobs["host_level"] = parent.level
        knobs["host_source"] = parent.knobs.get("source") or parent.level
        knobs["ir_join"] = 1
        knobs["champ"] = 1
        knobs["champ_cone"] = 1
        knobs["parent_extract_id"] = str((parent.knobs or {}).get("extract_id") or "")
    elif kind == "ir_cell_champ_cone_region":
        from .active import ir_cell_champ_cone_extract_cand, ir_cell_champ_cone_region_extract_cand

        knobs["source"] = "f4_ir_cell_champ_cone_region_extract"
        knobs["name"] = f"extract_ir_cell_champ_cone_region_{host}"
        knobs["host_level"] = parent.level
        knobs["host_source"] = parent.knobs.get("source") or parent.level
        knobs["ir_join"] = 1
        knobs["champ"] = 1
        knobs["champ_cone"] = 1
        knobs["region"] = region
        knobs["x_dbu"] = x_dbu
        knobs["y_dbu"] = y_dbu
        knobs["region_density"] = region_density if region_density is not None else 0.30
        prior = ir_cell_champ_cone_region_extract_cand(mem) or ir_cell_champ_cone_extract_cand(mem)
        knobs["parent_extract_id"] = (
            str((prior.knobs or {}).get("extract_id") or prior.id) if prior else ""
        )
    elif kind == "winning_ir_region":
        from .active import winning_ir_extract_cand, winning_ir_region_extract_cand

        knobs["source"] = "f4_winning_ir_region_extract"
        knobs["name"] = f"extract_winning_ir_region_{host}"
        knobs["host_level"] = parent.level
        knobs["host_source"] = parent.knobs.get("source") or parent.level
        knobs["ir_join"] = 1
        knobs["region"] = region
        knobs["x_dbu"] = x_dbu
        knobs["y_dbu"] = y_dbu
        knobs["region_density"] = region_density if region_density is not None else 0.30
        prior = winning_ir_region_extract_cand(mem) or winning_ir_extract_cand(mem)
        knobs["parent_extract_id"] = (
            str((prior.knobs or {}).get("extract_id") or prior.id) if prior else ""
        )
    elif refine_depth(kind, prefix="winning_ir_region_cell") is not None:
        _rd = refine_depth(kind, prefix="winning_ir_region_cell")
        knobs["source"] = refine_extract_source(_rd)
        knobs["name"] = f"extract_{kind}_{host}"
        knobs["host_level"] = parent.level
        knobs["host_source"] = parent.knobs.get("source") or parent.level
        knobs["ir_join"] = 1
        knobs[f"winning_ir_region{_refine_suffix(_rd)}"] = 1
        prior = _refine_prior_extract(mem, _rd)
        knobs["parent_extract_id"] = (
            str((prior.knobs or {}).get("extract_id") or prior.id)
            if prior
            else str((parent.knobs or {}).get("extract_id") or "")
        )
    elif region or x_dbu is not None:
        knobs["source"] = "f4_region_extract"
        knobs["region"] = region
        knobs["x_dbu"] = x_dbu
        knobs["y_dbu"] = y_dbu
        knobs["region_density"] = region_density if region_density is not None else 0.30
        knobs["name"] = f"extract_region_{parent.knobs.get('name')}"
    fp = knobs_fp("pdn", knobs)
    if fp in mem.seen_knobs("pdn"):
        return next(c for c in mem.by_level("pdn") if c.knobs_fp == fp)
    cid = DesignMemory.new_id()
    out_dir = REPO / "learn" / "sim" / "dse" / "extracts" / cid
    spec = resolve(design_id)
    ext = extract_pdn(
        Path(mapped),
        out_dir,
        top=spec.top,
        sdc=spec.constraint,
        util=util,
        density=density,
        timeout_s=timeout_s,
        x_dbu=x_dbu,
        y_dbu=y_dbu,
        region=region,
        region_density=region_density,
    )
    spice, insts = ext.get("spice"), ext.get("insts")
    dyn: dict = {}
    extract_cost = float(ext.get("cost_s") or 0.0)
    if ext.get("status") == "ok" and spice and insts:
        arr_dest = out_dir / "sta_arrivals.json"
        sta_p = Path(sta) if sta and Path(sta).is_file() else None
        if sta_p is None:
            arr = export_arrivals(Path(mapped), arr_dest, design_id=design_id)
            sta_p = arr_dest if arr.get("status") == "ok" and arr_dest.is_file() else None
            if sta_p:
                ext["n_sta_inst"] = arr.get("n_inst")
        if sta_p:
            ext["sta_arrivals"] = str(sta_p)
            ext["sta_via"] = "f4_host_arrivals" if sta else "extract"
        from .f4_oracle import n_r_from_spice

        n_r_ext = ext.get("n_r")
        dyn = solve_f4(
            variant=variant,
            pkg_r=pkg_r,
            pkg_l=pkg_l,
            c_decap=c_decap,
            i_scale=1.0,
            spice=spice,
            insts=insts,
            extract_kind="candidate",
            sta=sta_p,
            timeout_s=max(float(timeout_s), 90.0),
            n_r=int(n_r_ext) if n_r_ext is not None else n_r_from_spice(spice),
        )
        ext = {**ext, **{k: v for k, v in dyn.items() if k != "cost_s"}}
        ext["extract_cost_s"] = extract_cost
        ext["solve_cost_s"] = dyn.get("cost_s")
        ext["cost_s"] = extract_cost + float(dyn.get("cost_s") or 0.0)
    knobs["extract_id"] = cid
    em = (dyn.get("em") or ext.get("em") or {}) if isinstance(dyn, dict) else {}
    attr = attribute_dynamic_ir(ir_report_from_solve({**ext, **(dyn or {})}, insts=insts))
    attr["transform"] = host
    attr["inherited_from"] = parent.id
    attr["extract_id"] = cid
    if kind == "host":
        attr["via"] = "f4_host_extract"
        attr["host_level"] = parent.level
        attr["host_source"] = parent.knobs.get("source") or parent.level
    if kind == "host_region":
        attr["via"] = "f4_host_region_extract"
        attr["host_level"] = parent.level
        attr["host_source"] = parent.knobs.get("source") or parent.level
    if kind == "ir_cell":
        from .acquire import latest_host_extract_cand

        attr["via"] = "f4_ir_cell_extract"
        attr["host_level"] = parent.level
        attr["host_source"] = parent.knobs.get("source") or parent.level
        hx = latest_host_extract_cand(mem)
        if hx and hx.qor.dynamic_ir_mv is not None and ext.get("worst_droop_mv") is not None:
            attr["residual_mv"] = _residual_mv(ext, hx)
            attr["residual_vs"] = hx.id
            attr["residual_via"] = "ir_cell_vs_host_extract"
    if kind == "ir_cell_region":
        from .active import ir_cell_extract_cand

        attr["via"] = "f4_ir_cell_region_extract"
        attr["host_level"] = parent.level
        attr["host_source"] = parent.knobs.get("source") or parent.level
        ice = ir_cell_extract_cand(mem)
        if ice and ice.qor.dynamic_ir_mv is not None and ext.get("worst_droop_mv") is not None:
            attr["residual_mv"] = _residual_mv(ext, ice)
            attr["residual_vs"] = ice.id
            attr["residual_via"] = "ir_cell_region_vs_ir_cell_extract"
    if kind == "ir_cell_champ":
        from .active import ir_cell_extract_cand

        attr["via"] = "f4_ir_cell_champ_extract"
        attr["host_level"] = parent.level
        attr["host_source"] = parent.knobs.get("source") or parent.level
        ice = ir_cell_extract_cand(mem)
        if ice and ice.qor.dynamic_ir_mv is not None and ext.get("worst_droop_mv") is not None:
            attr["residual_mv"] = _residual_mv(ext, ice)
            attr["residual_vs"] = ice.id
            attr["residual_via"] = "ir_cell_champ_vs_ir_cell_extract"
    if kind == "ir_cell_champ_cone":
        from .active import ir_cell_champ_extract_cand

        attr["via"] = "f4_ir_cell_champ_cone_extract"
        attr["host_level"] = parent.level
        attr["host_source"] = parent.knobs.get("source") or parent.level
        ice = ir_cell_champ_extract_cand(mem)
        if ice and ice.qor.dynamic_ir_mv is not None and ext.get("worst_droop_mv") is not None:
            attr["residual_mv"] = _residual_mv(ext, ice)
            attr["residual_vs"] = ice.id
            attr["residual_via"] = "ir_cell_champ_cone_vs_ir_cell_champ_extract"
    if kind == "ir_cell_champ_cone_region":
        from .active import ir_cell_champ_cone_extract_cand, ir_cell_champ_cone_region_extract_cand

        attr["via"] = "f4_ir_cell_champ_cone_region_extract"
        attr["host_level"] = parent.level
        attr["host_source"] = parent.knobs.get("source") or parent.level
        prior = ir_cell_champ_cone_region_extract_cand(mem) or ir_cell_champ_cone_extract_cand(mem)
        if prior and prior.qor.dynamic_ir_mv is not None and ext.get("worst_droop_mv") is not None:
            attr["residual_mv"] = _residual_mv(ext, prior)
            attr["residual_vs"] = prior.id
            attr["residual_via"] = (
                "ir_cell_champ_cone_region_vs_prior_region"
                if (prior.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract"
                else "ir_cell_champ_cone_region_vs_ir_cell_champ_cone_extract"
            )
    if kind == "winning_ir_region":
        from .active import winning_ir_extract_cand, winning_ir_region_extract_cand

        attr["via"] = "f4_winning_ir_region_extract"
        attr["host_level"] = parent.level
        attr["host_source"] = parent.knobs.get("source") or parent.level
        prior = winning_ir_region_extract_cand(mem) or winning_ir_extract_cand(mem)
        if prior and prior.qor.dynamic_ir_mv is not None and ext.get("worst_droop_mv") is not None:
            attr["residual_mv"] = _residual_mv(ext, prior)
            attr["residual_vs"] = prior.id
            attr["residual_via"] = (
                "winning_ir_region_vs_prior_region"
                if (prior.knobs or {}).get("source") == "f4_winning_ir_region_extract"
                else "winning_ir_region_vs_winning_ir_extract"
            )
    if refine_depth(kind, prefix="winning_ir_region_cell") is not None:
        _rd = refine_depth(kind, prefix="winning_ir_region_cell")
        attr["via"] = refine_extract_source(_rd)
        attr["host_level"] = parent.level
        attr["host_source"] = parent.knobs.get("source") or parent.level
        prior = _refine_prior_extract(mem, _rd)
        if prior and prior.qor.dynamic_ir_mv is not None and ext.get("worst_droop_mv") is not None:
            attr["residual_mv"] = _residual_mv(ext, prior)
            attr["residual_vs"] = prior.id
            prev = (
                f"winning_ir_region_cell{_refine_suffix(_rd - 1)}_extract"
                if _rd >= 1
                else "winning_ir_region_extract"
            )
            attr["residual_via"] = f"{kind}_vs_{prev}"
    attr = _stamp_f4_attr(attr, ext if ext else dyn)
    kind_note = {
        "host": "host",
        "host_region": "host-region",
        "ir_cell": "IR-cell",
        "ir_cell_region": "IR-cell-region",
        "ir_cell_champ": "IR-cell-champ",
        "ir_cell_champ_cone": "IR-cell-champ-cone",
        "ir_cell_champ_cone_region": "IR-cell-champ-cone-region",
        "winning_ir_region": "winning-IR-region",
    }.get(kind) or (
        refine_label(refine_depth(kind, prefix="winning_ir_region_cell"))
        if refine_depth(kind, prefix="winning_ir_region_cell") is not None
        else "candidate"
    )
    q = QoR(
        congestion=ext.get("overflow"),
        static_ir_mv=ext.get("static_ir_mv") or dyn.get("static_ir_mv"),
        dynamic_ir_mv=ext.get("worst_droop_mv"),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        fidelity="F4",
        note=(
            f"{kind_note} write_pg_spice "
            f"n_r={ext.get('n_r')} droop={ext.get('worst_droop_mv')} "
            "— not finish, not gold"
        ),
    )
    inherit_parent_pd(q, parent.qor)
    ok = ext.get("status") == "ok" and (not dyn or dyn.get("status") == "ok")
    if ok and ext.get("worst_droop_mv") is not None and kind in (
        "candidate",
        "host",
        "ir_cell",
        "ir_cell_champ",
        "ir_cell_champ_cone",
    ):
        parent.qor.dynamic_ir_mv = float(ext["worst_droop_mv"])
        if ext.get("static_ir_mv") is not None or dyn.get("static_ir_mv") is not None:
            parent.qor.static_ir_mv = float(ext.get("static_ir_mv") or dyn["static_ir_mv"])
        if em.get("j_absmax_a_m2") is not None:
            parent.qor.em_j_a_m2 = float(em["j_absmax_a_m2"])
        parent.attr = dict(parent.attr or {})
        parent.attr["f4_extract"] = {
            "extract_id": cid,
            "n_r": ext.get("n_r"),
            "droop_mv": ext.get("worst_droop_mv"),
            "static_ir_mv": ext.get("static_ir_mv") or dyn.get("static_ir_mv"),
            "em_j_a_m2": em.get("j_absmax_a_m2"),
        }
        mem.touch(parent)
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent.id,
        level="pdn",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F4",
        qor=q,
        cost_s=float(ext.get("cost_s") or 0.0),
        artifacts=ext,
        attr=attr,
        status="ok" if ok else "fail",
        failure=ext.get("reason") if not ok else None,
        note=f"F4 extract of {host} n_r={ext.get('n_r')} droop={ext.get('worst_droop_mv')}",
    )
    added = mem.add(c)
    if persist_hotspot_join(added):
        mem.touch(added)
    return added


def ingest_f2(variant: str, mem: DesignMemory, design_id: str = "gcd") -> Candidate | None:
    """Place / GRT / finish metrics from an existing ORFS run. No new P&R."""
    finish = _read_json(orfs_logs(variant) / "6_report.json")
    grt = orfs_logs(variant) / "5_1_grt.log"
    dp = orfs_logs(variant) / "3_5_place_dp.log"
    if not finish and not grt.is_file() and not dp.is_file():
        return None
    knobs = {"source": "ingest_f2_orfs", "variant": variant}
    fp = knobs_fp("physical", knobs)
    if fp in mem.seen_knobs("physical"):
        return next(c for c in mem.by_level("physical") if c.knobs_fp == fp)
    overflow = None
    usage = None
    wl = None
    if grt.is_file():
        text = grt.read_text(errors="replace")
        m = re.search(
            r"^Total\s+(\d+)\s+(\d+)\s+([0-9.]+)%\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
            text,
            re.M,
        )
        if m:
            usage = float(m.group(3)) / 100.0
            overflow = float(m.group(6))
        wm = re.search(r"Total wirelength:\s+([0-9.]+)", text)
        if wm:
            wl = float(wm.group(1))
    hpwl = None
    if dp.is_file():
        hm = re.search(r"Final HPWL\s+([0-9.]+)", dp.read_text(errors="replace"))
        if hm:
            hpwl = float(hm.group(1))
    area = None
    n_cells = None
    power = None
    slack = None
    util = None
    leakage = None
    internal = None
    switching = None
    if finish:
        area = finish.get("finish__design__instance__area")
        n_cells = finish.get("finish__design__instance__count")
        power = finish.get("finish__power__total")
        slack = finish.get("finish__timing__setup__ws")
        util = finish.get("finish__design__instance__utilization")
        leakage = finish.get("finish__power__leakage")
        internal = finish.get("finish__power__internal")
        switching = finish.get("finish__power__switching")
    cong = overflow if overflow is not None else usage
    q = QoR(
        area_um2=float(area) if area is not None else None,
        n_cells=float(n_cells) if n_cells is not None else None,
        power_w=float(power) if power is not None else None,
        leakage_w=float(leakage) if leakage is not None else None,
        internal_power_w=float(internal) if internal is not None else None,
        switching_power_w=float(switching) if switching is not None else None,
        wns_cost=wns_cost_from_slack_ns(float(slack)) if slack is not None else None,
        congestion=float(cong) if cong is not None else None,
        hpwl_um=float(hpwl) if hpwl is not None else None,
        wirelength_um=float(wl) if wl is not None else None,
        core_util=core_util_from_report(util),
        fidelity="F2",
        note=(
            f"ORFS ingest HPWL={hpwl} GRT_wl={wl} util={util} overflow={overflow} "
            "— not a new place"
        ),
    )
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=None,
        level="physical",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(design_rtl(design_id)),
        netlist_fp=sha256_file(orfs_results(variant) / "1_2_yosys.v")
        if (orfs_results(variant) / "1_2_yosys.v").is_file()
        else None,
        fidelity="F2",
        qor=q,
        cost_s=0.0,
        note="F2 ingest of place/GRT/finish — controller did not launch P&R",
    )
    return mem.add(c)


def _read_verilog_block(rtl: Path | list[Path], include_dirs: list[Path] | None = None) -> str:
    files = list(rtl) if isinstance(rtl, (list, tuple)) else [rtl]
    inc = "".join(f" -I{d}" for d in (include_dirs or []))
    return "\n".join(f"read_verilog{inc} {f}" for f in files)


def _f1_yscript(
    rtl: Path | list[Path],
    top: str,
    lib: str,
    map_cmd: str,
    net: Path,
    hier: Path | None,
    knobs: dict,
    abc_file: Path | None = None,
    *,
    equiv: bool = True,
    include_dirs: list[Path] | None = None,
) -> str:
    """Chip F1 flattens first (area teacher 409.108). Cone F1 keeps hierarchy.

    Equiv is always on generic synth *before* liberty map — Nangate cells
    have no SAT model. Architecture extracts use flatten-first even when
    `scope=logic_cone`. Cone ABC requires `cone=dpath|ctrl` / `cone_module`.
    """
    reads = _read_verilog_block(rtl, include_dirs)
    cone = is_cone_abc(knobs)
    if not cone:
        body = f"""
{reads}
hierarchy -check -top {top}
proc; flatten; opt_expr; opt_clean
design -save rtl
synth -top {top}
design -save syn
"""
        if equiv:
            body += f"""
design -copy-from rtl -as gold {top}
design -copy-from syn -as gate {top}
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple
equiv_induct
equiv_status
"""
        body += f"""
design -load syn
dfflibmap -liberty {lib}
{map_cmd}
techmap; opt_clean
stat -liberty {lib}
write_verilog -noattr -noexpr {net}
"""
        return body
    from .arch_space import cone_modules_for, leftover_modules

    cone_mods = cone_modules_for(knobs)
    leftover = leftover_modules(cone_mods, top=top)
    hier_w = f"write_verilog -noattr -noexpr {hier}" if hier else ""

    def _map_mods(mods: list[str], cmd: str) -> str:
        return "".join(f"cd {m}\ndfflibmap -liberty {lib}\n{cmd}\ncd ..\n" for m in mods)

    body = f"""
{reads}
hierarchy -check -top {top}
proc; opt_expr; opt_clean
design -save rtl_hier
flatten
design -save rtl
synth -top {top}
design -save syn
"""
    if equiv:
        body += f"""
design -copy-from rtl -as gold {top}
design -copy-from syn -as gate {top}
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple
equiv_induct
equiv_status
"""
    body += f"""
design -load rtl_hier
synth -top {top}
{_map_mods(cone_mods, map_cmd)}
hierarchy -top {top}
{_map_mods(leftover, f"abc -liberty {lib}")}
hierarchy -top {top}
techmap; opt_clean
{hier_w}
flatten
stat -liberty {lib}
write_verilog -noattr -noexpr {net}
"""
    return body


def evaluate_f1_abc(
    *,
    rtl: Path,
    liberty: Path,
    knobs: dict,
    mem: DesignMemory,
    design_id: str = "gcd",
    parent_id: str | None = None,
    timeout_s: float = 60.0,
    level: str = "logic",
    top: str = "gcd",
) -> Candidate:
    """Yosys synth + liberty ABC + equiv vs RTL. ABC script is a *file* (not -p ';')."""
    knobs = dict(knobs)
    if level == "synthesis":
        knobs.pop("abc_ops", None)
    spec = resolve(design_id)
    if not spec.f1_ready:
        raise ValueError(f"{design_id} F1 needs {spec.hdl} frontend — not inventing a Verilog remap")
    files, incs = rtl_inputs(Path(rtl), design_id)
    timeout_s = max(float(timeout_s), float(spec.f1_timeout_s))
    want_equiv = bool(spec.f1_equiv)
    ops = list(knobs.get("abc_ops") or [])
    args = list(knobs.get("abc_args") or [])
    fp = knobs_fp(level, knobs)
    t0 = time.time()
    lib = str(liberty)
    with tempfile.TemporaryDirectory(prefix="dse-f1-") as tmp:
        tmp_p = Path(tmp)
        log = tmp_p / "yosys.log"
        net = tmp_p / "mapped.v"
        ys = tmp_p / "f1.ys"
        abc_file = tmp_p / "aig.abc"
        hier = tmp_p / "hier.v"
        map_cmd = "abc -liberty " + lib
        if args:
            map_cmd += " " + " ".join(args)
        if ops:
            write_abc_script(ops, abc_file, map_liberty=True)
            map_cmd += f" -script {abc_file}"
        ys.write_text(
            _f1_yscript(
                files,
                top,
                lib,
                map_cmd,
                net,
                hier,
                knobs,
                abc_file,
                equiv=want_equiv,
                include_dirs=incs,
            )
        )
        proc = subprocess.run(
            ["yosys", "-q", "-l", str(log), "-s", str(ys)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        text = log.read_text(errors="replace") if log.is_file() else (proc.stdout or "") + (proc.stderr or "")
        area, n_cells = _parse_stat(text, top)
        equiv = bool(
            re.search(r"Equivalence successfully proven", text, re.I)
            or re.search(r"are proven and 0 are unproven", text, re.I)
        )
        net_fp = sha256_file(net) if net.is_file() else sha256_text(text[-2000:])
        err = next((ln.strip() for ln in text.splitlines() if "ERROR" in ln), "")
        mapped_text = net.read_text() if net.is_file() else None
        hier_text = hier.read_text() if hier.is_file() else None
    cost = time.time() - t0
    ok = area is not None and proc.returncode == 0 and (equiv if want_equiv else True)
    fail = None if ok else (err or ("equiv_or_map_failed" if want_equiv else "map_failed"))
    cid = DesignMemory.new_id()
    artifacts: dict = {}
    if mapped_text and ok:
        dest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cid}.v"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(mapped_text)
        artifacts["mapped_v"] = str(dest)
        try:
            artifacts.update(net_features(parse_mapped_verilog(dest)))
        except Exception:
            pass
        if hier_text:
            hdest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cid}.hier.v"
            hdest.write_text(hier_text)
            artifacts["mapped_hier_v"] = str(hdest)
            artifacts["hierarchy"] = True
            artifacts["cone"] = knobs.get("cone") or knobs.get("scope")
    if n_cells is None:
        n_cells = artifacts.get("n_cells")
    q = QoR(
        area_um2=area,
        n_cells=n_cells,
        fidelity="F1",
        note=(
            "Yosys+ABC ORFS abc_speed.script (ABC_AREA=0); stdcell area; delay/IR not claimed from F1"
            if level == "synthesis"
            else (
                f"Yosys+ABC cone-local map on {knobs.get('cone') or 'named'} modules; stdcell area; delay/IR not claimed from F1"
                if is_cone_abc(knobs)
                else "Yosys+ABC mapped stdcell area; delay/IR not claimed from F1"
            )
        ),
    )
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent_id,
        level=level,
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(rtl),
        netlist_fp=net_fp,
        fidelity="F1",
        qor=q,
        cost_s=cost,
        artifacts=artifacts,
        status="ok" if ok else "fail",
        failure=fail,
        note=f"F1 {knobs.get('name')} equiv={'PASS' if equiv else ('SKIP' if not want_equiv else 'FAIL')}"
        + (f" · cone {knobs.get('cone') or knobs.get('cone_module')}" if is_cone_abc(knobs) else "")
        + (" · ORFS abc_speed" if level == "synthesis" else "")
        + (f" · {err}" if err and not ok else ""),
    )
    return mem.add(c)


def evaluate_f1_synth(
    *,
    rtl: Path,
    liberty: Path,
    mem: DesignMemory,
    design_id: str = "gcd",
    parent_id: str | None = None,
    timeout_s: float = 90.0,
    top: str = "gcd",
    knobs: dict | None = None,
) -> Candidate:
    """ORFS ``abc_speed.script`` + ``-D 460``. Not logic ``-fast``, not ``abc_ops``."""
    from .synthesis import synth_f1_knobs

    k = {**synth_f1_knobs(), **dict(knobs or {})}
    k.pop("abc_ops", None)
    k.setdefault("abc_args", synth_f1_knobs()["abc_args"])
    k.setdefault("abc_script", "file")
    k.setdefault("name", "orfs_abc_speed")
    k.setdefault("abcArea", 0)
    k.setdefault("source", "orfs_abc_script")
    return evaluate_f1_abc(
        rtl=rtl,
        liberty=liberty,
        knobs=k,
        mem=mem,
        design_id=design_id,
        parent_id=parent_id,
        timeout_s=timeout_s,
        level="synthesis",
        top=top,
    )


def ensure_mapped_netlist(
    cand: Candidate,
    *,
    rtl: Path,
    liberty: Path,
    top: str = "gcd",
    timeout_s: float = 60.0,
) -> Candidate:
    """Resume-safe: re-map F1 rows that lack cells or were written without -noexpr."""
    existing = (cand.artifacts or {}).get("mapped_v")
    if existing and Path(existing).is_file() and is_gate_cell_netlist(Path(existing)):
        return cand
    dest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cand.id}.v"
    dest.parent.mkdir(parents=True, exist_ok=True)
    knobs = cand.knobs or {}
    ops = list(knobs.get("abc_ops") or [])
    args = list(knobs.get("abc_args") or [])
    lib = str(liberty)
    src_rtl = Path(rtl)
    extract = knobs.get("extract")
    spec = resolve(str(cand.design_id or "gcd"))
    with tempfile.TemporaryDirectory(prefix="dse-map-") as tmp:
        tmp_p = Path(tmp)
        net = tmp_p / "mapped.v"
        ys = tmp_p / "map.ys"
        abc_file = tmp_p / "aig.abc"
        map_cmd = "abc -liberty " + lib
        if args:
            map_cmd += " " + " ".join(args)
        if ops:
            write_abc_script(ops, abc_file, map_liberty=True)
            map_cmd += f" -script {abc_file}"
        if extract and spec.arch_extracts:
            from .arch_space import emit_gcd_variant

            variant = tmp_p / "variant.v"
            try:
                emit_gcd_variant(src_rtl, str(extract), variant)
                src_rtl = variant
            except ValueError:
                pass
        files, incs = rtl_inputs(src_rtl, spec.id)
        if extract and spec.arch_extracts:
            files, incs = [src_rtl], list(spec.include_dirs)
        hier = tmp_p / "hier.v"
        ys.write_text(
            _f1_yscript(
                files,
                top,
                lib,
                map_cmd,
                net,
                hier,
                knobs,
                abc_file,
                equiv=False,
                include_dirs=incs,
            )
        )
        proc = subprocess.run(
            ["yosys", "-q", "-s", str(ys)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if proc.returncode != 0 or not net.is_file():
            return cand
        dest.write_text(net.read_text())
        if hier.is_file():
            hdest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cand.id}.hier.v"
            hdest.write_text(hier.read_text())
            art_h = str(hdest)
        else:
            art_h = None
    art = dict(cand.artifacts or {})
    art["mapped_v"] = str(dest)
    if art_h:
        art["mapped_hier_v"] = art_h
        art["hierarchy"] = True
    try:
        art.update(net_features(parse_mapped_verilog(dest)))
    except Exception:
        pass
    cand.artifacts = art
    return cand


def evaluate_f2_fast(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    util: float = 0.35,
) -> Candidate | None:
    """F2-fast on a persisted F1 netlist. Separate physical observation, no P&R."""
    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    knobs = {
        "source": "f2_fast_netgraph",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "util": util,
        "rev": 2,
    }
    fp = knobs_fp("physical", knobs)
    if fp in mem.seen_knobs("physical"):
        return next(c for c in mem.by_level("physical") if c.knobs_fp == fp)
    t0 = time.time()
    est = estimate_physical(Path(mapped), util=util)
    est = dict(est)
    est["mapped_v"] = mapped
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=est.get("n_cells"),
        congestion=est.get("congestion"),
        fidelity="F2",
        note=(
            f"F2-fast HPWL={est['hpwl']:.3f} grid · rudy_excess={est.get('rudy_excess', 0):.3f} "
            f"· {est['via']}"
        ),
    )
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=parent.id,
        level="physical",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F2",
        qor=q,
        cost_s=time.time() - t0,
        artifacts=est,
        attr={
            "transform": parent.knobs.get("name"),
            "context": {"parent": parent.id, "level": parent.level},
            "note": "transform+netlist → ΔHPWL/RUDY; not Dynamic IR",
        },
        note=f"F2-fast child of {parent.knobs.get('name')} HPWL={est['hpwl']:.3f}",
    )
    return mem.add(c)


def evaluate_f2_gpl(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 45.0,
    extra_knobs: dict | None = None,
) -> Candidate | None:
    """Budgeted OpenROAD GPL on a gate-level F1 netlist. Not finish, not IR."""
    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    knobs = {
        "source": "f2_openroad_gpl",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "util": util,
        "density": density,
        "skip_io": True,
    }
    if extra_knobs:
        # Catalog / region tags only — never ABC/PDN knobs on this fingerprint.
        for k in (
            "catalog",
            "coreUtilization",
            "placeDensityAddon",
            "region",
            "x_dbu",
            "y_dbu",
            "region_density",
        ):
            if k in extra_knobs:
                knobs[k] = extra_knobs[k]
    if knobs.get("region") or knobs.get("x_dbu") is not None:
        knobs["source"] = "f2_openroad_gpl_region"
    fp = knobs_fp("physical", knobs)
    if fp in mem.seen_knobs("physical"):
        return next(c for c in mem.by_level("physical") if c.knobs_fp == fp)
    spec = resolve(design_id)
    gpl = evaluate_gpl(
        Path(mapped),
        top=spec.top,
        util=util,
        density=density,
        timeout_s=timeout_s,
        x_dbu=knobs.get("x_dbu"),
        y_dbu=knobs.get("y_dbu"),
        region=knobs.get("region"),
        region_density=knobs.get("region_density"),
    )
    q = QoR(
        area_um2=gpl.get("inst_area_um2") or parent.qor.area_um2,
        n_cells=gpl.get("n_inst") or parent.qor.n_cells,
        congestion=gpl.get("overflow"),
        hpwl_um=gpl.get("hpwl_um"),
        fidelity="F2",
        note=(
            f"OpenROAD GPL HPWL={gpl.get('hpwl_um')} um overflow={gpl.get('overflow')} "
            f"— not GRT, not F5, not IR"
        ),
    )
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=parent.id,
        level="physical",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F2",
        qor=q,
        cost_s=float(gpl.get("cost_s") or 0.0),
        artifacts=gpl,
        attr={
            "transform": parent.knobs.get("name"),
            "context": {"parent": parent.id, "level": parent.level},
            "note": "transform+netlist → OpenROAD GPL; not Dynamic IR",
        },
        status="ok" if gpl.get("status") == "ok" else "fail",
        failure=gpl.get("reason") if gpl.get("status") != "ok" else None,
        note=f"F2 GPL child of {parent.knobs.get('name')} HPWL_um={gpl.get('hpwl_um')}",
    )
    return mem.add(c)


def evaluate_f3_sta(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
) -> Candidate | None:
    """F3 OpenSTA on a gate-level F1 netlist. Enriches the parent QoR."""
    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    hier = (parent.artifacts or {}).get("mapped_hier_v")
    sta_v = Path(hier) if hier and Path(hier).is_file() else Path(mapped)
    knobs = {
        "source": "f3_opensta_ideal",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "interconnect": "ideal",
        "hierarchy": bool(hier and Path(hier).is_file()),
    }
    fp = knobs_fp(parent.level, knobs)
    if fp in mem.seen_knobs(parent.level):
        return next(c for c in mem.by_level(parent.level) if c.knobs_fp == fp)
    sta = evaluate_sta(sta_v, design_id=design_id)
    from .attribute import attribute_sta

    attr = attribute_sta(sta, inherit=parent.attr or {})
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=parent.qor.n_cells,
        fidelity="F3",
        note=(
            f"OpenSTA ideal WNS={sta.get('wns_ns')} ns P={sta.get('power_w')} W "
            f"leak={sta.get('leakage_w')} W "
            f"{'(hier paths)' if knobs.get('hierarchy') else ''} — not SPEF signoff, not IR"
        ),
    )
    merge_sta_into_qor(q, sta)
    if sta.get("status") == "ok":
        enrich_parent_qor_from(parent.qor, q)
        parent.attr = dict(parent.attr or {})
        parent.attr["sta"] = attr
        mem.touch(parent)
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=parent.id,
        level=parent.level,
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F3",
        qor=q,
        cost_s=float(sta.get("cost_s") or 0.0),
        artifacts=sta,
        attr=attr,
        status="ok" if sta.get("status") == "ok" else "fail",
        failure=sta.get("reason") if sta.get("status") != "ok" else None,
        note=f"F3 STA child of {parent.knobs.get('name')} WNS={sta.get('wns_ns')}",
    )
    return mem.add(c)


def evaluate_cell_size(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    cells: list[str] | None = None,
    top: str = "gcd",
    source: str = "cell_size_up",
    extract_id: str | None = None,
) -> Candidate | None:
    """Upsize attributed cells.

    source=cell_size_ir is the I-scale-win IR-hotspot ODB join.
    source=cell_size_ir_champ is the I-scale-champ join (not the first ctrl set).
    source=cell_size_ir_champ_cone is leftover cells on the champ extract
    (not the champ size-up set). extract_id stamps the champ extract so a
    later R-graph can re-pay leftover-cone size-up — not a session-global one-shot.
    source=cell_size_ir_winning_region is leftover combo cells on the
    winning-IR-region PDN join (not leftover-cone, not champ ctrl).
    source=cell_size_ir_winning_region_leftover is leftover leftover cells on the
    leftover-combo PDN join (not leftover-combo flatten, not leftover-cone).
    source=cell_size_ir_winning_region_leftover2 is leftover leftover leftover cells on the
    leftover leftover PDN join (not leftover leftover flatten, not leftover-combo).
    """
    spec = resolve(design_id)
    if top == "gcd":
        top = spec.top
    from .attribute import attribute_sta
    from .cell_space import upsize_file
    from .sta_f3 import evaluate_sta

    mapped = (parent.artifacts or {}).get("mapped_v")
    hier = (parent.artifacts or {}).get("mapped_hier_v")
    src = Path(hier) if hier and Path(hier).is_file() else (Path(mapped) if mapped else None)
    if src is None or not src.is_file():
        return None
    targets = list(cells or [])
    if not targets:
        f3 = next(
            (
                c
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f3_opensta_ideal"
                and (c.knobs or {}).get("parent_id") == parent.id
            ),
            None,
        )
        art = (f3.artifacts if f3 else None) or {}
        targets = list(art.get("path_cells") or (parent.attr or {}).get("sta", {}).get("cells") or [])
        if not targets:
            for key in ("path_start", "path_end"):
                v = art.get(key) or (parent.attr or {}).get("sta", {}).get(key)
                if v:
                    targets.append(str(v))
    knobs = {
        "source": source,
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name") or parent.knobs.get("source"),
        "cells": targets,
        "step": 1,
    }
    if source == "cell_size_ir":
        knobs["ir_join"] = 1
    if source == "cell_size_ir_champ":
        knobs["ir_join"] = 1
        knobs["champ"] = 1
        if extract_id:
            knobs["extract_id"] = str(extract_id)
    if source == "cell_size_ir_champ_cone":
        knobs["ir_join"] = 1
        knobs["champ"] = 1
        knobs["champ_cone"] = 1
        if extract_id:
            knobs["extract_id"] = str(extract_id)
    _rd_src = refine_depth(source, prefix="cell_size_ir_winning_region")
    if _rd_src is not None:
        knobs["ir_join"] = 1
        knobs[f"winning_ir_region{_refine_suffix(_rd_src)}"] = 1
        if extract_id:
            knobs["extract_id"] = str(extract_id)
    fp = knobs_fp("cell", knobs)
    if fp in mem.seen_knobs("cell"):
        return next(c for c in mem.by_level("cell") if c.knobs_fp == fp)
    cid = DesignMemory.new_id()
    dest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cid}.v"
    sized = upsize_file(src, targets, dest, top=top)
    if sized.get("n_changed", 0) <= 0:
        return mem.add(
            Candidate(
                id=cid,
                design_id=design_id,
                parent_id=parent.id,
                level="cell",
                knobs=knobs,
                knobs_fp=fp,
                rtl_fp=parent.rtl_fp,
                netlist_fp=parent.netlist_fp,
                fidelity="F3",
                qor=QoR(fidelity="F3", note="no liberty drive step on the attributed cells"),
                cost_s=0.0,
                artifacts=sized,
                status="fail",
                failure="no_cell_drive_step",
                note="cell-local upsize found no X1/X2/X4 instance on the path",
            )
        )
    sta = evaluate_sta(dest, design_id=design_id)
    area = n_cells = None
    if dest.is_file() and NANGATE_LIB.is_file():
        try:
            proc = subprocess.run(
                [
                    "yosys",
                    "-p",
                    f"read_verilog {dest}; hierarchy -top {top}; stat -liberty {NANGATE_LIB}",
                ],
                capture_output=True,
                text=True,
                timeout=20.0,
            )
            area, n_cells = _parse_stat((proc.stdout or "") + (proc.stderr or ""), top)
        except (subprocess.TimeoutExpired, OSError):
            pass
    attr = attribute_sta(sta, inherit=parent.attr or {})
    attr["cells_changed"] = sized["changed"]
    attr["transform"] = source
    if source == "cell_size_ir":
        attr["via"] = "active_f4_ir_cell"
        attr["cells"] = list(targets)
        note = (
            f"IR-hotspot cell upsize n={sized['n_changed']} WNS={sta.get('wns_ns')} "
            "— ODB join, not STA path, not ABC"
        )
    elif source == "cell_size_ir_champ":
        attr["via"] = "active_f4_ir_cell_champ"
        attr["cells"] = list(targets)
        note = (
            f"I-scale-champ cell upsize n={sized['n_changed']} WNS={sta.get('wns_ns')} "
            "— ODB join on winning_ir_pdn activity, not first ctrl IR-cell, not STA path"
        )
    elif source == "cell_size_ir_champ_cone":
        attr["via"] = "active_f4_ir_cell_champ_cone"
        attr["cells"] = list(targets)
        note = (
            f"IR-cell-champ leftover-cone upsize n={sized['n_changed']} WNS={sta.get('wns_ns')} "
            "— champ-extract join minus champ size-up, not first ctrl IR-cell, not STA path"
        )
    elif refine_depth(source, prefix="cell_size_ir_winning_region") is not None:
        _rd = refine_depth(source, prefix="cell_size_ir_winning_region")
        attr["via"] = f"active_f4_winning_ir_region_cell{_refine_suffix(_rd)}"
        attr["cells"] = list(targets)
        note = (
            f"{refine_label(_rd)} upsize n={sized['n_changed']} WNS={sta.get('wns_ns')} "
            f"— refine[{_rd}] join minus sized lineage, not previous-depth flatten, not STA path"
        )
    else:
        note = (
            f"cell-local upsize n={sized['n_changed']} WNS={sta.get('wns_ns')} "
            "— attributed path, not ABC, not IR"
        )
    q = QoR(
        area_um2=area,
        n_cells=n_cells,
        fidelity="F3",
        note=note,
    )
    merge_sta_into_qor(q, sta)
    return mem.add(
        Candidate(
            id=cid,
            design_id=design_id,
            parent_id=parent.id,
            level="cell",
            knobs=knobs,
            knobs_fp=fp,
            rtl_fp=parent.rtl_fp,
            netlist_fp=sha256_file(dest),
            fidelity="F3",
            qor=q,
            cost_s=float(sta.get("cost_s") or 0.0),
            artifacts={**sta, **sized, "mapped_v": str(dest)},
            attr=attr,
            status="ok" if sta.get("status") == "ok" else "fail",
            failure=sta.get("reason") if sta.get("status") != "ok" else None,
            note=(
                f"cell size-up {sized['n_changed']} inst "
                f"WNS={sta.get('wns_ns')} vs parent {parent.knobs.get('name')}"
            ),
        )
    )


def evaluate_net_buffer(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    hops: list[str] | None = None,
    top: str = "gcd",
    source: str = "net_buffer",
) -> Candidate | None:
    """Insert BUF on attributed worst-path hops. Not ABC, not a cell drive-up."""
    spec = resolve(design_id)
    if top == "gcd":
        top = spec.top
    from .attribute import attribute_sta
    from .net_space import BUF_TYPE, buffer_file
    from .sta_f3 import evaluate_sta

    mapped = (parent.artifacts or {}).get("mapped_v")
    hier = (parent.artifacts or {}).get("mapped_hier_v")
    src = Path(hier) if hier and Path(hier).is_file() else (Path(mapped) if mapped else None)
    if src is None or not src.is_file():
        return None
    types: dict[str, str] = {}
    targets = list(hops or [])
    if not targets:
        f3 = next(
            (
                c
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f3_opensta_ideal"
                and (c.knobs or {}).get("parent_id") == parent.id
            ),
            None,
        )
        art = (f3.artifacts if f3 else None) or parent.artifacts or {}
        targets = list(art.get("path_nets") or (parent.attr or {}).get("nets") or [])
        types = dict(art.get("path_types") or {})
        if not types:
            types = dict((parent.artifacts or {}).get("path_types") or {})
    knobs = {
        "source": source,
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "hops": targets,
        "buf": BUF_TYPE,
    }
    if source == "net_buffer_spef":
        knobs["spef_residual"] = 1
    fp = knobs_fp("net", knobs)
    if fp in mem.seen_knobs("net"):
        return next(c for c in mem.by_level("net") if c.knobs_fp == fp)
    cid = DesignMemory.new_id()
    dest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cid}.v"
    bufd = buffer_file(src, targets, dest, top=top, path_types=types or None)
    if bufd.get("n_changed", 0) <= 0:
        return mem.add(
            Candidate(
                id=cid,
                design_id=design_id,
                parent_id=parent.id,
                level="net",
                knobs=knobs,
                knobs_fp=fp,
                rtl_fp=parent.rtl_fp,
                netlist_fp=parent.netlist_fp,
                fidelity="F3",
                qor=QoR(fidelity="F3", note="no intra-module combo hop to buffer"),
                cost_s=0.0,
                artifacts=bufd,
                status="fail",
                failure="no_net_buffer",
                note="net-local buffer found no intra-module combo hop",
            )
        )
    sta = evaluate_sta(dest, design_id=design_id)
    area = n_cells = None
    if dest.is_file() and NANGATE_LIB.is_file():
        try:
            proc = subprocess.run(
                [
                    "yosys",
                    "-p",
                    f"read_verilog {dest}; hierarchy -top {top}; stat -liberty {NANGATE_LIB}",
                ],
                capture_output=True,
                text=True,
                timeout=20.0,
            )
            area, n_cells = _parse_stat((proc.stdout or "") + (proc.stderr or ""), top)
        except (subprocess.TimeoutExpired, OSError):
            pass
    attr = attribute_sta(sta, inherit=parent.attr or {})
    attr["nets_changed"] = bufd["changed"]
    attr["transform"] = "net_buffer"
    attr["scope"] = "net"
    q = QoR(
        area_um2=area,
        n_cells=n_cells,
        fidelity="F3",
        note=(
            f"net-local BUF n={bufd['n_changed']} WNS={sta.get('wns_ns')} "
            "— attributed hops, not ABC, not IR"
        ),
    )
    merge_sta_into_qor(q, sta)
    return mem.add(
        Candidate(
            id=cid,
            design_id=design_id,
            parent_id=parent.id,
            level="net",
            knobs=knobs,
            knobs_fp=fp,
            rtl_fp=parent.rtl_fp,
            netlist_fp=sha256_file(dest),
            fidelity="F3",
            qor=q,
            cost_s=float(sta.get("cost_s") or 0.0),
            artifacts={**sta, **bufd, "mapped_v": str(dest)},
            attr=attr,
            status="ok" if sta.get("status") == "ok" else "fail",
            failure=sta.get("reason") if sta.get("status") != "ok" else None,
            note=(
                f"net buffer {bufd['n_changed']} hops "
                f"WNS={sta.get('wns_ns')} vs parent {parent.knobs.get('name')}"
            ),
        )
    )


def evaluate_net_port_buffer(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    hops: list[str] | None = None,
    top: str = "gcd",
) -> Candidate | None:
    """Insert BUF on attributed cross-module port nets. Not intra-module hops."""
    spec = resolve(design_id)
    if top == "gcd":
        top = spec.top
    from .attribute import attribute_sta
    from .net_space import BUF_TYPE, buffer_port_file, hop_is_block_port, hop_is_cross_module
    from .sta_f3 import evaluate_sta

    mapped = (parent.artifacts or {}).get("mapped_v")
    hier = (parent.artifacts or {}).get("mapped_hier_v")
    src = Path(hier) if hier and Path(hier).is_file() else (Path(mapped) if mapped else None)
    if src is None or not src.is_file():
        return None
    types: dict[str, str] = {}
    targets = [h for h in list(hops or []) if hop_is_block_port(h)]
    if not targets:
        from .acquire import _attributed_cross_module_nets

        targets = list(_attributed_cross_module_nets(mem))
        block = [h for h in targets if hop_is_block_port(h)]
        if block:
            targets = block
    if not targets:
        targets = [h for h in list(hops or []) if hop_is_cross_module(h)]
    if not types:
        for c in reversed(list(mem.all())):
            if c.status != "ok":
                continue
            art = c.artifacts or {}
            if any(hop_is_block_port(str(h)) for h in list(art.get("path_nets") or [])):
                types = dict(art.get("path_types") or {})
                if types:
                    break
    knobs = {
        "source": "net_buffer_port",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "hops": targets,
        "buf": BUF_TYPE,
        "scope": "port",
        "cross_module": 1,
    }
    fp = knobs_fp("net", knobs)
    if fp in mem.seen_knobs("net"):
        return next(c for c in mem.by_level("net") if c.knobs_fp == fp)
    cid = DesignMemory.new_id()
    dest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cid}.v"
    bufd = buffer_port_file(src, targets, dest, top=top, path_types=types or None)
    if bufd.get("n_changed", 0) <= 0:
        return mem.add(
            Candidate(
                id=cid,
                design_id=design_id,
                parent_id=parent.id,
                level="net",
                knobs=knobs,
                knobs_fp=fp,
                rtl_fp=parent.rtl_fp,
                netlist_fp=parent.netlist_fp,
                fidelity="F3",
                qor=QoR(fidelity="F3", note="no cross-module port net to buffer"),
                cost_s=0.0,
                artifacts=bufd,
                status="fail",
                failure="no_net_port",
                note="port-net buffer found no ctrl↔dpath (or cross-submodule) hop",
            )
        )
    sta = evaluate_sta(dest, design_id=design_id)
    area = n_cells = None
    if dest.is_file() and NANGATE_LIB.is_file():
        try:
            proc = subprocess.run(
                [
                    "yosys",
                    "-p",
                    f"read_verilog {dest}; hierarchy -top {top}; stat -liberty {NANGATE_LIB}",
                ],
                capture_output=True,
                text=True,
                timeout=20.0,
            )
            area, n_cells = _parse_stat((proc.stdout or "") + (proc.stderr or ""), top)
        except (subprocess.TimeoutExpired, OSError):
            pass
    attr = attribute_sta(sta, inherit=parent.attr or {})
    attr["nets_changed"] = bufd["changed"]
    attr["transform"] = "net_buffer_port"
    attr["scope"] = "port"
    q = QoR(
        area_um2=area,
        n_cells=n_cells,
        fidelity="F3",
        note=(
            f"port-net BUF n={bufd['n_changed']} WNS={sta.get('wns_ns')} "
            "— parent-scoped crossing, not intra-module, not ABC"
        ),
    )
    merge_sta_into_qor(q, sta)
    return mem.add(
        Candidate(
            id=cid,
            design_id=design_id,
            parent_id=parent.id,
            level="net",
            knobs=knobs,
            knobs_fp=fp,
            rtl_fp=parent.rtl_fp,
            netlist_fp=sha256_file(dest),
            fidelity="F3",
            qor=q,
            cost_s=float(sta.get("cost_s") or 0.0),
            artifacts={**sta, **bufd, "mapped_v": str(dest), "mapped_hier_v": str(dest)},
            attr=attr,
            status="ok" if sta.get("status") == "ok" else "fail",
            failure=sta.get("reason") if sta.get("status") != "ok" else None,
            note=(
                f"port-net buffer {bufd['n_changed']} hops "
                f"WNS={sta.get('wns_ns')} vs parent {parent.knobs.get('name')}"
            ),
        )
    )


def evaluate_f2_grt(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 45.0,
) -> Candidate | None:
    """Routing-level F2: GRT after place_pins+GPL. Not detailed route, not F5."""
    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    knobs = {
        "source": "f2_openroad_grt",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "util": util,
        "density": density,
    }
    fp = knobs_fp("routing", knobs)
    if fp in mem.seen_knobs("routing"):
        return next(c for c in mem.by_level("routing") if c.knobs_fp == fp)
    cid = DesignMemory.new_id()
    sdf_dest = REPO / "learn" / "sim" / "dse" / "sdf" / f"{cid}.sdf"
    spec = resolve(design_id)
    grt = evaluate_grt(
        Path(mapped),
        top=spec.top,
        sdc=spec.constraint,
        util=util,
        density=density,
        timeout_s=timeout_s,
        sdf_out=sdf_dest,
    )
    from .attribute import attribute_sta

    attr = attribute_sta(grt, inherit=parent.attr or {})
    cong = grt.get("grt_overflow")
    if cong is None:
        cong = grt.get("overflow")
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=parent.qor.n_cells,
        congestion=cong,
        fidelity="F2",
        note=(
            f"OpenROAD GRT WNS={grt.get('wns_ns')} overflow={cong} "
            f"HPWL={grt.get('hpwl_um')} — not detailed route/F5, not IR"
        ),
    )
    merge_sta_into_qor(q, grt)
    if grt.get("sdf"):
        grt = dict(grt)
        parent.artifacts = dict(parent.artifacts or {})
        parent.artifacts["sdf"] = grt["sdf"]
        mem.touch(parent)
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent.id,
        level="routing",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F2",
        qor=q,
        cost_s=float(grt.get("cost_s") or 0.0),
        artifacts=grt,
        attr=attr,
        status="ok" if grt.get("status") == "ok" else "fail",
        failure=grt.get("reason") if grt.get("status") != "ok" else None,
        note=f"F2 GRT child of {parent.knobs.get('name')} WNS={grt.get('wns_ns')}",
    )
    return mem.add(c)


def evaluate_f3_sdf(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    sdf: Path | str | None = None,
) -> Candidate | None:
    """OpenSTA + GRT SDF on the same mapped netlist. Not OpenRCX SPEF, not F5."""
    mapped = (parent.artifacts or {}).get("mapped_v")
    sdf_p = Path(sdf) if sdf else Path((parent.artifacts or {}).get("sdf") or "")
    if not mapped or not Path(mapped).is_file() or not sdf_p.is_file():
        return None
    knobs = {
        "source": "f3_opensta_sdf_grt",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "interconnect": "sdf_grt",
    }
    fp = knobs_fp(parent.level, knobs)
    if fp in mem.seen_knobs(parent.level):
        return next(c for c in mem.by_level(parent.level) if c.knobs_fp == fp)
    sta = evaluate_sta(Path(mapped), sdf=sdf_p, design_id=design_id)
    from .attribute import attribute_sta

    attr = attribute_sta(sta, inherit=parent.attr or {})
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=parent.qor.n_cells,
        fidelity="F3",
        note=(
            f"OpenSTA + GRT SDF WNS={sta.get('wns_ns')} ns — not SPEF/OpenRCX, not finish/F5"
        ),
    )
    merge_sta_into_qor(q, sta)
    if sta.get("status") == "ok":
        parent.attr = dict(parent.attr or {})
        parent.attr["sta_sdf"] = attr
        parent.artifacts = dict(parent.artifacts or {})
        parent.artifacts["sdf_wns_ns"] = sta.get("wns_ns")
        mem.touch(parent)
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=parent.id,
        level=parent.level,
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F3",
        qor=q,
        cost_s=float(sta.get("cost_s") or 0.0),
        artifacts=sta,
        attr=attr,
        status="ok" if sta.get("status") == "ok" else "fail",
        failure=sta.get("reason") if sta.get("status") != "ok" else None,
        note=f"F3 SDF-GRT child of {parent.knobs.get('name')} WNS={sta.get('wns_ns')}",
    )
    return mem.add(c)


def evaluate_f5_drt(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 45.0,
) -> Candidate | None:
    """F5-lite: detailed_route + OpenRCX SPEF. Not make finish. Clock ideal."""
    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    spec = resolve(design_id)
    knobs = {
        "source": "f5_openroad_drt_rcx",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "util": util,
        "density": density,
        "droute_end_iter": 2,
        "clock": "ideal",
        "top": spec.top,
        "sdc": str(spec.constraint),
        "special_pg": 2,
    }
    fp = knobs_fp("routing", knobs)
    if fp in mem.seen_knobs("routing"):
        prev = next(c for c in mem.by_level("routing") if c.knobs_fp == fp)
        if prev.status == "ok":
            return prev
    cid = DesignMemory.new_id()
    spef_dest = REPO / "learn" / "sim" / "dse" / "spef" / f"{cid}.spef"
    raw = run_f5_drt(
        Path(mapped),
        top=spec.top,
        sdc=spec.constraint,
        util=util,
        density=density,
        timeout_s=timeout_s,
        spef_out=spef_dest,
    )
    sta = {}
    if raw.get("status") == "ok" and raw.get("spef"):
        sta = evaluate_sta(Path(mapped), spef=Path(raw["spef"]), design_id=design_id)
        raw = _overlay_sta(raw, sta)
        raw["interconnect"] = sta.get("interconnect") or "spef_openrcx"
    from .attribute import attribute_sta

    attr = attribute_sta(sta or raw, inherit=parent.attr or {})
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=parent.qor.n_cells,
        congestion=raw.get("grt_overflow"),
        hpwl_um=raw.get("hpwl_um"),
        fidelity="F5",
        note=(
            f"OpenRCX SPEF WNS={raw.get('wns_ns')} segs={raw.get('n_rc_segments')} "
            "— F5-lite, not make finish, clock ideal"
        ),
    )
    merge_sta_into_qor(q, sta or raw)
    if raw.get("spef"):
        parent.artifacts = dict(parent.artifacts or {})
        parent.artifacts["spef"] = raw["spef"]
        if raw.get("wns_ns") is not None:
            parent.artifacts["spef_wns_ns"] = raw["wns_ns"]
        mem.touch(parent)
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent.id,
        level="routing",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F5",
        qor=q,
        cost_s=float(raw.get("cost_s") or 0.0) + float(sta.get("cost_s") or 0.0),
        artifacts=raw,
        attr=attr,
        status="ok" if raw.get("status") == "ok" else "fail",
        failure=raw.get("reason") if raw.get("status") != "ok" else None,
        note=f"F5 DRT+RCX child of {parent.knobs.get('name')} WNS={raw.get('wns_ns')}",
    )
    return mem.add(c)


def evaluate_f5_local(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 45.0,
) -> Candidate | None:
    """F5 OpenRCX SPEF on a cell/net netlist. Not the F1 F5-lite SPEF.

    Same DRT+RCX oracle as F5-lite, different knobs (`source=f5_openroad_local`).
    Does not overwrite an existing F1 SPEF on a shared parent.
    """
    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    host_src = (parent.knobs or {}).get("source")
    host_level = "port" if host_src == "net_buffer_port" else parent.level
    knobs = {
        "source": "f5_openroad_local",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name") or parent.knobs.get("source"),
        "host_level": host_level,
        "host_source": host_src,
        "util": util,
        "density": density,
        "droute_end_iter": 2,
        "clock": "ideal",
    }
    fp = knobs_fp("routing", knobs)
    if fp in mem.seen_knobs("routing"):
        return next(c for c in mem.by_level("routing") if c.knobs_fp == fp)
    spec = resolve(design_id)
    cid = DesignMemory.new_id()
    spef_dest = REPO / "learn" / "sim" / "dse" / "spef" / f"{cid}_local.spef"
    raw = run_f5_drt(
        Path(mapped),
        top=spec.top,
        sdc=spec.constraint,
        util=util,
        density=density,
        timeout_s=timeout_s,
        spef_out=spef_dest,
    )
    sta = {}
    if raw.get("status") == "ok" and raw.get("spef"):
        sta = evaluate_sta(Path(mapped), spef=Path(raw["spef"]), design_id=design_id)
        raw = _overlay_sta(raw, sta)
        raw["interconnect"] = sta.get("interconnect") or "spef_openrcx"
        raw["ideal_wns_ns"] = (parent.artifacts or {}).get("wns_ns")
        raw["host_level"] = host_level
    from .attribute import attribute_sta

    attr = attribute_sta(sta or raw, inherit=parent.attr or {})
    attr["transform"] = "f5_local_spef"
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=parent.qor.n_cells,
        congestion=raw.get("grt_overflow"),
        hpwl_um=raw.get("hpwl_um"),
        fidelity="F5",
        note=(
            f"local OpenRCX SPEF WNS={raw.get('wns_ns')} on {host_level} "
            f"(ideal {raw.get('ideal_wns_ns')}) — not F1 F5-lite, not make finish"
        ),
    )
    merge_sta_into_qor(q, sta or raw)
    if raw.get("spef"):
        parent.artifacts = dict(parent.artifacts or {})
        parent.artifacts["spef_local"] = raw["spef"]
        if raw.get("wns_ns") is not None:
            parent.artifacts["spef_local_wns_ns"] = raw["wns_ns"]
        mem.touch(parent)
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent.id,
        level="routing",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F5",
        qor=q,
        cost_s=float(raw.get("cost_s") or 0.0) + float(sta.get("cost_s") or 0.0),
        artifacts=raw,
        attr=attr,
        status="ok" if raw.get("status") == "ok" else "fail",
        failure=raw.get("reason") if raw.get("status") != "ok" else None,
        note=(
            f"F5 local SPEF child of {parent.level}/{(parent.knobs or {}).get('source')} "
            f"WNS={raw.get('wns_ns')}"
        ),
    )
    return mem.add(c)


def evaluate_f5_cts(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 90.0,
) -> Candidate | None:
    """F5-CTS: clock_tree_synthesis + DRT + OpenRCX. Not make finish.

    Distinct knobs from F5-lite (`clock=propagated`, `cts=1`). Does not
    overwrite the parent's F5-lite SPEF — that stays the ideal-clock artifact.
    """
    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    knobs = {
        "source": "f5_openroad_cts_rcx",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "util": util,
        "density": density,
        "droute_end_iter": 2,
        "clock": "propagated",
        "cts": 1,
    }
    fp = knobs_fp("routing", knobs)
    if fp in mem.seen_knobs("routing"):
        return next(c for c in mem.by_level("routing") if c.knobs_fp == fp)
    cid = DesignMemory.new_id()
    spef_dest = REPO / "learn" / "sim" / "dse" / "spef" / f"{cid}_cts.spef"
    v_dest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cid}_cts.v"
    raw = run_f5_cts(
        Path(mapped),
        util=util,
        density=density,
        timeout_s=timeout_s,
        spef_out=spef_dest,
        verilog_out=v_dest,
    )
    sta = {}
    sta_v = Path(raw["cts_v"]) if raw.get("cts_v") else Path(mapped)
    if raw.get("status") == "ok" and raw.get("spef"):
        sta = evaluate_sta(sta_v, spef=Path(raw["spef"]), propagated_clock=True, design_id=design_id)
        raw = _overlay_sta(raw, sta)
        raw["interconnect"] = sta.get("interconnect") or "spef_openrcx"
        raw["clock"] = "propagated"
    from .attribute import attribute_sta

    attr = attribute_sta(sta or raw, inherit=parent.attr or {})
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=parent.qor.n_cells,
        congestion=raw.get("grt_overflow"),
        hpwl_um=raw.get("hpwl_um"),
        fidelity="F5",
        note=(
            f"CTS SPEF WNS={raw.get('wns_ns')} n_clkbuf={raw.get('n_clkbuf')} "
            "— F5-CTS, not make finish, clock propagated"
        ),
    )
    merge_sta_into_qor(q, sta or raw)
    if raw.get("spef"):
        parent.artifacts = dict(parent.artifacts or {})
        parent.artifacts["spef_cts"] = raw["spef"]
        if raw.get("cts_v"):
            parent.artifacts["cts_v"] = raw["cts_v"]
        if raw.get("wns_ns") is not None:
            parent.artifacts["spef_cts_wns_ns"] = raw["wns_ns"]
        mem.touch(parent)
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent.id,
        level="routing",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F5",
        qor=q,
        cost_s=float(raw.get("cost_s") or 0.0) + float(sta.get("cost_s") or 0.0),
        artifacts=raw,
        attr=attr,
        status="ok" if raw.get("status") == "ok" else "fail",
        failure=raw.get("reason") if raw.get("status") != "ok" else None,
        note=f"F5 CTS+RCX child of {parent.knobs.get('name')} WNS={raw.get('wns_ns')}",
    )
    return mem.add(c)


def evaluate_f3_spef(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    spef: Path | str | None = None,
) -> Candidate | None:
    """OpenSTA + OpenRCX SPEF on the same mapped netlist. Not finish."""
    mapped = (parent.artifacts or {}).get("mapped_v")
    spef_p = Path(spef) if spef else Path((parent.artifacts or {}).get("spef") or "")
    if not mapped or not Path(mapped).is_file() or not spef_p.is_file():
        return None
    knobs = {
        "source": "f3_opensta_spef",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "interconnect": "spef",
    }
    fp = knobs_fp(parent.level, knobs)
    if fp in mem.seen_knobs(parent.level):
        return next(c for c in mem.by_level(parent.level) if c.knobs_fp == fp)
    sta = evaluate_sta(Path(mapped), spef=spef_p, design_id=design_id)
    from .attribute import attribute_sta

    attr = attribute_sta(sta, inherit=parent.attr or {})
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=parent.qor.n_cells,
        fidelity="F3",
        note=f"OpenSTA + OpenRCX SPEF WNS={sta.get('wns_ns')} ns — not finish/F5 launch",
    )
    merge_sta_into_qor(q, sta)
    if sta.get("status") == "ok":
        parent.attr = dict(parent.attr or {})
        parent.attr["sta_spef"] = attr
        parent.artifacts = dict(parent.artifacts or {})
        parent.artifacts["spef_wns_ns"] = sta.get("wns_ns")
        mem.touch(parent)
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=parent.id,
        level=parent.level,
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F3",
        qor=q,
        cost_s=float(sta.get("cost_s") or 0.0),
        artifacts=sta,
        attr=attr,
        status="ok" if sta.get("status") == "ok" else "fail",
        failure=sta.get("reason") if sta.get("status") != "ok" else None,
        note=f"F3 SPEF child of {parent.knobs.get('name')} WNS={sta.get('wns_ns')}",
    )
    return mem.add(c)


def _parse_stat(text: str, top: str = "gcd") -> tuple[float | None, float | None]:
    area = None
    cells = None
    for m in re.finditer(rf"Chip area for (?:top )?module '\\{top}':\s+([0-9.]+)", text):
        area = float(m.group(1))
    # Prefer the last cell count that sits near a gcd/top area line
    for m in re.finditer(r"Number of cells:\s+([0-9]+)", text):
        cells = float(m.group(1))
    return area, cells


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _mv(frac_or_none, mv_or_none) -> float | None:
    if mv_or_none is not None:
        return float(mv_or_none)
    if frac_or_none is None:
        return None
    v = float(frac_or_none)
    if v < 1.0:  # volts of droop
        return v * 1e3
    return v


def liberty_path() -> Path:
    env = os.environ.get("STA_LIB") or os.environ.get("DSE_LIB")
    if env and Path(env).is_file():
        return Path(env)
    return NANGATE_LIB

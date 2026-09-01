"""Budget-aware DSE controller. One level per proposal — never a flat box.

Loop: inspect → propose (level, knobs) → pick fidelity → evaluate → attribute
→ update memory / Pareto → next.

Optimizers (each on its own level):
  architecture — e-graph extract of the IR-attributed dpath cone (ROVER/ASPEN shape)
  logic        — BOiLS SSK-GP + EHVI(area, WNS) / EI, DRiLLS sequential append
  logic_ctrl   — cone-local ABC on the attributed FSM (not leftover of dpath)
  synthesis    — ORFS ABC_AREA F0 catalog + one abc_speed.script F1 (not abc_ops)
  cell         — attributed worst-path drive-up (module-scoped; not ABC)
  net          — attributed worst-path BUF insert (module-scoped; not ABC)
  net_port     — parent-scoped BUF on ctrl↔dpath port nets, including bus bits (not intra-module hops)
  physical     — F2-fast + budgeted GPL + AutoDMP catalog GPL + ingest + F0 proxy
  routing      — budgeted OpenROAD GRT + F5-lite DRT/OpenRCX + paid F5-CTS (not make finish)
  active       — F3→F5 residual + F4 IR residual loop (region decap, then unused pkg L)
  pdn          — F4 ingest + candidate write_pg_spice + host extract + host-region density cap + host IR-steer + IR-cell extract residual + DirectLU/AMG/RAS/Krylov + unused Dynamic IR catalog on a strap/EM winning_ir extract + unused catalog on leftover leftover leftover extract after winning family + AMG/RAS/Krylov on winning_ir_pdn + static-IR pkg_r then on-die bump pitch then metal4 straps then EM width + I-scale of the attributed host (not gold)

Acquisition ≈ expected improvement + information − compute − extrapolation risk.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from .abc_space import CATALOG
from .acquire import (
    latest_ok_extract,
    latest_ok_host_extract,
    latest_host_arrivals,
    latest_host_extract_cand,
    should_pay_ctrl_cone,
    extract_on_disk,
)
from .active import (
    iscale_host,
    winning_host_pdn,
    winning_ir_pdn,
    winning_static_pdn,
    winning_em_pdn,
)
from .arch_space import emit_gcd_variant, stamp_cone_knobs
from .designs import resolve
from .attribute import attribute_from_path, local_scope, persist_hotspot_join
from .dispatch import run_next_refine
from .boils import propose_logic_boils, should_pay_f1
from .fidelity import (
    evaluate_cell_size,
    evaluate_f1_abc,
    evaluate_f3_sta,
    evaluate_f4_extract,
    evaluate_f4_pdn,
    evaluate_f4_static_mesh,
    evaluate_f4_static_straps,
    evaluate_f4_em_straps,
    evaluate_f4_scale,
    evaluate_host_arrivals,
    ensure_mapped_netlist,
    flowlab_params,
    ingest_f2,
    ingest_pdn,
    ingest_physical,
    liberty_path,
    reports_dir,
)
from .costs import estimated_cost_s
from .fingerprint import knobs_fp
from .f4_oracle import ir_run_labels, n_r_from_spice, spice_paths
from .layers import adapter_status
from .netgraph import is_gate_cell_netlist
from .memory import Candidate, DesignMemory
from .metrics import QoR, pareto_front, qor_delta
from .mo import baseline_wns, timing_of
from .resources import admit_solve
from .solve_result import stamp_f4_candidate
from .stages import (
    STAGES_F4_HEAD,
    STAGES_IR_CELL,
    STAGES_IR_CHAMP,
    STAGES_IR_INSPECT,
    STAGES_IR_REGION_CELL,
    STAGES_IR_SOLVERS,
    STAGES_IR_STEER,
    STAGES_LOGIC_TRANSFORM,
    STAGES_PLACE_ROUTE,
    STAGES_STEER_GAP,
    run_stage,
)
from .pdn_space import GOLD_KNOBS, next_pdn_spec
from .physical_space import gpl_density, propose_synthesis_f0
from .planner import plan_search, rank_extracts, next_candidate_ids
from .proposer import propose as propose_from_attr
from .surrogate import (
    predict_f1_area,
    predict_f2_from_f1,
    predict_f2_gnn,
    predict_f4_from_f1,
    predict_gpl_from_f1,
    predict_power_from_f1,
    predict_wns_from_f1,
    predict_f5_from_f1,
    predict_f5_cts_from_f1,
    residual_f3_to_f5_lite,
    residual_f3_to_f5_local,
    residual_f4_knob,
    residual_f4_mesh,
    residual_f4_region,
    residual_f4_host_region,
    residual_f4_static,
    residual_f4_static_mesh,
    residual_f4_static_straps,
    residual_f4_em,
    residual,
)

LEVELS = ("architecture", "logic", "synthesis", "cell", "net", "physical", "routing", "pdn")


def propose_logic(mem: DesignMemory, focus: str = "chip") -> dict | None:
    """Public hook used by tests: a logic proposal never carries physical knobs."""
    return propose_logic_boils(mem, focus=focus)


def _logic_cone_focus(plan: dict, attr: dict, *, design_id: str = "gcd") -> str:
    """Prefer dpath cone ABC when both modules are on the path. Ctrl is a later shot.

    GCD cone names stay in GCD fixtures — aes/ibex never invent dpath/ctrl.
    """
    from .designs import resolve

    spec = resolve(design_id)
    mods = list(attr.get("modules") or [])
    focus = str(plan.get("focus") or "chip")
    if spec.has_cone("dpath") and ("dpath" in mods or focus == "dpath"):
        return "dpath"
    if spec.has_cone("ctrl") and ("ctrl" in mods or focus == "ctrl"):
        return "ctrl"
    return focus


def f1_ok(mem: DesignMemory) -> list:
    return [
        c
        for c in mem.all()
        if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None
    ]


def f1_area_winner(mem: DesignMemory):
    xs = f1_ok(mem)
    return min(xs, key=lambda c: float(c.qor.area_um2)) if xs else None


def f1_wns_winner(mem: DesignMemory):
    """F1 with the best joined F3 slack. None if nobody has been timed."""
    xs = []
    for c in f1_ok(mem):
        wns, _ = timing_of(mem, c)
        if wns is not None:
            xs.append((wns, c))
    return min(xs, key=lambda t: t[0])[1] if xs else None


def f1_pareto_parents(mem: DesignMemory) -> list:
    """Area-best and WNS-best F1 (one row if they coincide). Not a flat knob vector."""
    out = []
    seen = set()
    for c in (f1_area_winner(mem), f1_wns_winner(mem)):
        if c and c.id not in seen:
            out.append(c)
            seen.add(c.id)
    return out


def _mapped_pick(cands, *, rtl, liberty, top: str = "gcd"):
    for cand in cands:
        if cand is None:
            continue
        w = ensure_mapped_netlist(cand, rtl=rtl, liberty=liberty, top=top)
        mapped = (w.artifacts or {}).get("mapped_v")
        if mapped and is_gate_cell_netlist(Path(mapped)):
            return w
    return None


def _refine_report(mem: DesignMemory) -> list[dict]:
    """Studio-facing refine[N] frames. Legacy leftover2 keys stay for replay."""
    from .frame import leftover_cells, refine_chain, refine_label

    out: list[dict] = []
    for f in refine_chain(mem):
        mods = []
        if f.cell is not None:
            mods = list(
                dict.fromkeys(
                    str(x).split("/")[0]
                    for x in (f.cell.knobs or {}).get("cells") or []
                    if "/" in str(x)
                )
            )
        cat = f.catalog[-1] if f.catalog else None
        out.append(
            {
                "depth": f.depth,
                "label": f"refine[{f.depth}]",
                "legacy": refine_label(f.depth),
                "n_cells": len(f.cells),
                "modules": ",".join(mods) if mods else None,
                "extract_id": f.extract_id or None,
                "extract_mv": (
                    float(f.extract.qor.dynamic_ir_mv)
                    if f.extract is not None and f.extract.qor.dynamic_ir_mv is not None
                    else None
                ),
                "pdn_mv": (
                    float(f.pdn.qor.dynamic_ir_mv)
                    if f.pdn is not None and f.pdn.qor.dynamic_ir_mv is not None
                    else None
                ),
                "pdn_name": (
                    str((f.pdn.knobs or {}).get("name") or "") if f.pdn is not None else None
                ),
                "catalog_mv": (
                    float(cat.qor.dynamic_ir_mv)
                    if cat is not None and cat.qor.dynamic_ir_mv is not None
                    else None
                ),
                "catalog_name": (
                    str((cat.knobs or {}).get("name") or "") if cat is not None else None
                ),
                "leftover_n": len(leftover_cells(mem, f.depth)),
            }
        )
    return out


def n_r_of_extract(
    mem: DesignMemory,
    *,
    extract_id: str | None = None,
    extract_hit: dict | None = None,
    spice: Path | str | None = None,
    variant: str = "flowlab",
    design_id: str = "gcd",
) -> int | None:
    """Mesh size from a recorded extract, then the spice file. Missing stays missing."""
    if extract_hit:
        if extract_hit.get("n_r") is not None:
            return int(extract_hit["n_r"])
        cand = extract_hit.get("candidate")
        if cand is not None and (cand.artifacts or {}).get("n_r") is not None:
            return int(cand.artifacts["n_r"])
        if extract_hit.get("spice"):
            nr = n_r_from_spice(extract_hit["spice"])
            if nr:
                return nr
    if extract_id:
        hit = extract_on_disk(mem, str(extract_id))
        if hit and hit.get("n_r") is not None:
            return int(hit["n_r"])
        for c in mem.by_level("pdn"):
            art = c.artifacts or {}
            if art.get("n_r") is None:
                continue
            if c.id == extract_id or str((c.knobs or {}).get("extract_id") or "") == str(extract_id):
                return int(art["n_r"])
    if spice:
        nr = n_r_from_spice(spice)
        if nr:
            return nr
    return n_r_from_spice(spice_paths(variant, design_id).get("spice"))


def admit_paid_f4(
    mem: DesignMemory,
    *,
    solver: str,
    extract_id: str | None = None,
    extract_hit: dict | None = None,
    spice: Path | str | None = None,
    n_r: int | None = None,
    n_nodes: int | None = None,
    step=None,
    fidelity: str = "F4",
    variant: str = "flowlab",
    design_id: str = "gcd",
) -> dict:
    """Controller-side F4 gate. Logs step("admit", why=gate.reason). Does not launch."""
    if n_r is None:
        n_r = n_r_of_extract(
            mem,
            extract_id=extract_id,
            extract_hit=extract_hit,
            spice=spice,
            variant=variant,
            design_id=design_id,
        )
    if n_nodes is None and isinstance(extract_hit, dict):
        cand = extract_hit.get("candidate")
        art = (cand.artifacts if cand is not None else {}) or {}
        if art.get("n_nodes") is not None:
            n_nodes = int(art["n_nodes"])
        elif extract_hit.get("n_nodes") is not None:
            n_nodes = int(extract_hit["n_nodes"])
    gate = admit_solve(n_r, n_nodes=n_nodes, solver=solver)
    why = gate.get("reason") or f"admit {gate.get('solver')} n_r={n_r}"
    if step is not None:
        step(
            "admit",
            fidelity=fidelity,
            pay=bool(gate.get("admitted")),
            why=why,
            solver=gate.get("solver"),
            n_r=n_r,
        )
    return gate


def run_controller(
    *,
    variant: str = "flowlab",
    budget_s: float = 45.0,
    f1_max: int = 6,
    design_id: str = "gcd",
    rtl: Path | None = None,
    memory_path: Path | None = None,
    fresh: bool = False,
    arch_max: int = 3,
    max_shots: dict | None = None,
) -> dict:
    t_end = time.time() + max(float(budget_s), 1.0)
    root = Path(__file__).resolve().parents[1].parent
    spec = resolve(design_id)
    rtl = Path(rtl) if rtl else spec.rtl
    top = spec.top
    mem_path = Path(memory_path) if memory_path else root / "learn" / "sim" / "dse" / f"memory_{variant}.jsonl"
    if fresh and mem_path.is_file():
        mem_path.unlink()
        idx = mem_path.with_suffix(".index.json")
        if idx.is_file():
            idx.unlink()
    mem = DesignMemory(mem_path)
    lib = liberty_path()
    log: list[dict] = []

    def step(kind: str, **kw):
        log.append({"t": time.time(), "kind": kind, **kw})

    from . import fidelity as _fid

    _raw_f4_pdn = _fid.evaluate_f4_pdn
    _raw_f4_extract = _fid.evaluate_f4_extract
    _raw_f4_scale = _fid.evaluate_f4_scale
    _raw_f4_static_mesh = _fid.evaluate_f4_static_mesh
    _raw_f4_static_straps = _fid.evaluate_f4_static_straps
    _raw_f4_em_straps = _fid.evaluate_f4_em_straps

    def evaluate_f4_pdn(*args, **kwargs):
        solver = kwargs.get("solver") or "direct"
        gate = admit_paid_f4(
            mem,
            solver=solver,
            extract_id=kwargs.get("extract_id"),
            spice=kwargs.get("spice"),
            step=step,
            fidelity="F4",
            variant=variant,
            design_id=design_id,
        )
        if not gate.get("admitted"):
            return None
        child = _raw_f4_pdn(*args, **kwargs)
        if child:
            stamp_f4_candidate(child)
        return child

    def evaluate_f4_extract(*args, **kwargs):
        gate = admit_paid_f4(
            mem,
            solver="direct",
            step=step,
            fidelity="F4_EXTRACT",
            variant=variant,
            design_id=design_id,
        )
        if not gate.get("admitted"):
            return None
        child = _raw_f4_extract(*args, **kwargs)
        if child:
            stamp_f4_candidate(child)
        return child

    def evaluate_f4_scale(*args, **kwargs):
        gate = admit_paid_f4(
            mem,
            solver="direct",
            extract_id=kwargs.get("extract_id"),
            spice=kwargs.get("spice"),
            step=step,
            fidelity="F4_SCALE",
            variant=variant,
            design_id=design_id,
        )
        if not gate.get("admitted"):
            return None
        child = _raw_f4_scale(*args, **kwargs)
        if child:
            stamp_f4_candidate(child)
        return child

    def evaluate_f4_static_mesh(*args, **kwargs):
        gate = admit_paid_f4(
            mem,
            solver="direct",
            extract_id=kwargs.get("parent_extract_id"),
            step=step,
            fidelity="F4_STATIC_MESH",
            variant=variant,
            design_id=design_id,
        )
        if not gate.get("admitted"):
            return None
        child = _raw_f4_static_mesh(*args, **kwargs)
        if child:
            stamp_f4_candidate(child)
        return child

    def evaluate_f4_static_straps(*args, **kwargs):
        gate = admit_paid_f4(
            mem,
            solver="direct",
            extract_id=kwargs.get("parent_extract_id"),
            step=step,
            fidelity="F4_STATIC_STRAPS",
            variant=variant,
            design_id=design_id,
        )
        if not gate.get("admitted"):
            return None
        child = _raw_f4_static_straps(*args, **kwargs)
        if child:
            stamp_f4_candidate(child)
        return child

    def evaluate_f4_em_straps(*args, **kwargs):
        gate = admit_paid_f4(
            mem,
            solver="direct",
            extract_id=kwargs.get("parent_extract_id"),
            step=step,
            fidelity="F4_EM_STRAPS",
            variant=variant,
            design_id=design_id,
        )
        if not gate.get("admitted"):
            return None
        child = _raw_f4_em_straps(*args, **kwargs)
        if child:
            stamp_f4_candidate(child)
        return child

    def time_candidate(cand, *, reason: str):
        """Interleave F3 so WNS can steer the next extract / ABC sequence."""
        if cand is None or cand.status != "ok":
            return None
        if time.time() + estimated_cost_s(mem, "F3", design_id, cost_key="F3") > t_end:
            return None
        n_have = sum(
            1
            for c in mem.all()
            if (c.knobs or {}).get("source") == "f3_opensta_ideal" and c.status == "ok"
        )
        sta_max = int((max_shots or {}).get("f3", 8))
        if n_have >= sta_max:
            return None
        if any(
            (c.knobs or {}).get("source") == "f3_opensta_ideal"
            and (c.knobs or {}).get("parent_id") == cand.id
            and c.status == "ok"
            for c in mem.all()
        ):
            return None
        w = ensure_mapped_netlist(cand, rtl=rtl, liberty=lib, top=top)
        mem.touch(w)
        child = evaluate_f3_sta(w, mem, design_id=design_id)
        if child:
            step(
                "evaluate",
                id=child.id,
                level=w.level,
                fidelity="F3",
                via="f3_interleave",
                parent=w.id,
                wns_ns=(child.artifacts or {}).get("wns_ns"),
                power_w=child.qor.power_w,
                status=child.status,
                reason=reason,
            )
        return child

    step("inspect", n=len(mem), levels=sorted({c.level for c in mem.all()}))
    from .activity import load_activity, persist_activity

    act = load_activity(variant=variant, design_id=design_id)
    if act:
        persist_activity(act, variant=variant, design_id=design_id)
        step("inspect", activity=act.get("via"), n_inst=act.get("n_inst"), n_toggle=act.get("n_toggle"))
    from .f4_oracle import solver_devices as _solver_devices

    step("inspect", solver_devices=_solver_devices())
    n_join = 0
    for c in mem.by_level("pdn"):
        if c.status != "ok":
            continue
        src = str((c.knobs or {}).get("source") or "")
        via = str((c.attr or {}).get("via") or "")
        refine_extract = src.startswith("f4_winning_ir_region_cell") and src.endswith("_extract")
        refine_restamp = via.startswith("active_f4_winning_ir_region_cell") and (
            via.endswith("_pdn") or via.endswith("_catalog")
        )
        if src not in (
            "f4_iscale_champ",
            "f4_em_strap_extract",
            "f4_static_strap_extract",
            "f4_winning_ir_region_extract",
        ) and via != "active_f4_winning_ir_pdn" and not refine_extract and not refine_restamp:
            continue
        if persist_hotspot_join(c):
            mem.touch(c)
            n_join += 1
    if n_join:
        step("inspect", persist_hotspot_join=n_join, via="odb-geom")
    phys = ingest_physical(variant, mem, design_id)
    if phys:
        step("ingest", level="physical", id=phys.id, fidelity=phys.fidelity)
    f2 = ingest_f2(variant, mem, design_id)
    if f2:
        step("ingest", level="physical", id=f2.id, fidelity="F2")
    pdn = ingest_pdn(variant, mem, design_id)
    if pdn:
        step("ingest", level="pdn", id=pdn.id, fidelity=pdn.fidelity)

    ir_json = reports_dir(variant) / f"dynamic_ir_{variant}.json"
    attr = attribute_from_path(ir_json)
    focus = local_scope(attr)
    for c in (pdn, phys, f2):
        if c:
            c.attr = attr
            mem.touch(c)

    f2_cong = f2.qor.congestion if f2 and f2.qor.congestion is not None else None
    plan = plan_search(attr, mem, f2_cong=f2_cong, design_id=design_id)
    step("plan", **{k: plan[k] for k in ("focus", "combo_frac", "f2_cong") if k in plan})
    for s in plan["steps"]:
        step("plan_step", **s)

    def _synth_f1_done() -> bool:
        return any(c.level == "synthesis" and c.fidelity == "F1" for c in mem.all())

    def _f1_room() -> int:
        """Reserve one F1 slot for ORFS abc_speed until that layer is measured."""
        return f1_max - (0 if _synth_f1_done() else 1)

    n_f1 = sum(1 for c in mem.all() if c.fidelity == "F1")
    n_arch = sum(1 for c in mem.by_level("architecture") if c.fidelity == "F1")

    # Seed the logic baseline first so architecture ΔQoR has a teacher.
    if not spec.f1_ready:
        step(
            "acquire",
            fidelity="F1",
            pay=False,
            why=f"{design_id} F1 needs {spec.hdl} frontend — not inventing a Verilog remap",
        )
    if spec.f1_ready and n_f1 < f1_max and time.time() < t_end:
        seed = {
            "name": "liberty_default",
            "abc_args": [],
            "abc_ops": [],
            "abc_script": "file",
        }
        if knobs_fp("logic", seed) not in mem.seen_knobs("logic"):
            step("propose", level="logic", knobs=seed, fidelity="F1", why="baseline teacher")
            cand = evaluate_f1_abc(
                rtl=rtl,
                liberty=lib,
                knobs=seed,
                mem=mem,
                design_id=design_id,
                parent_id=phys.id if phys else None,
                level="logic",
                top=top,
            )
            cand.attr = {
                "inherited_from": "physical_ir",
                "scope": focus.get("scope"),
                "modules": focus.get("modules"),
                "transform": "liberty_default",
                "note": "F1 baseline; attribution is context from F4",
            }
            mem.touch(cand)
            n_f1 += 1
            step(
                "evaluate",
                id=cand.id,
                level="logic",
                fidelity="F1",
                status=cand.status,
                area_um2=cand.qor.area_um2,
                cost_s=cand.cost_s,
            )
            time_candidate(cand, reason="F3 teacher on liberty_default before extracts")

    # Re-plan once WNS exists so logic acquisition is EHVI, not area-only EI.
    plan = plan_search(attr, mem, f2_cong=f2_cong, design_id=design_id)

    # Hierarchical architecture: planner orders extracts from IR attribution.
    arch_step = next((s for s in plan["steps"] if s["level"] == "architecture"), None)
    if spec.arch_extracts and arch_step and time.time() < t_end:
        from .arch_space import plan_dpath_extracts

        _eg, _roots, _ex, stats = plan_dpath_extracts()
        step("egraph", **{k: stats[k] for k in ("n_enodes", "n_eclasses", "rules_fired", "extracts")})
        step("arch_reason", reason=arch_step.get("reason"))
        arch_skip: set[str] = set()
        while n_arch < arch_max and n_f1 < _f1_room() and time.time() < t_end:
            remaining = [
                e
                for e in rank_extracts(list(_ex), mem, combo=float(plan.get("combo_frac") or 0.0))
                if e not in arch_skip
            ]
            if not remaining:
                break
            name = remaining[0]
            knobs = {
                "name": name,
                "module": "dpath",
                "extract": name,
                "scope": "logic_cone",
                "abc_script": "file",
            }
            if knobs_fp("architecture", knobs) in mem.seen_knobs("architecture"):
                arch_skip.add(name)
                continue
            if time.time() + estimated_cost_s(mem, "F1", design_id, cost_key="F1") > t_end and n_f1:
                step("stop", reason="budget would not cover architecture F1")
                break
            with tempfile.TemporaryDirectory(prefix="dse-arch-") as tmp:
                dest = Path(tmp) / f"gcd_{name}.v"
                try:
                    meta = emit_gcd_variant(rtl, name, dest)
                except ValueError as exc:
                    arch_skip.add(name)
                    step("arch_skip", extract=name, reason=str(exc))
                    continue
                step("propose", level="architecture", knobs=knobs, fidelity="F1")
                cand = evaluate_f1_abc(
                    rtl=dest,
                    liberty=lib,
                    knobs=knobs,
                    mem=mem,
                    design_id=design_id,
                    parent_id=phys.id if phys else None,
                    level="architecture",
                    top=top,
                )
            cand.egraph = stats
            cand.attr = {
                "transform": name,
                "context": focus,
                "inherited_from": "physical_ir",
                "scope": "logic_cone",
                "modules": ["dpath"],
                "operator": meta.get("operator"),
                "note": "cone-local extract; F1 equiv vs this RTL, not a chip restart",
            }
            _attach_delta(cand, mem)
            mem.touch(cand)
            n_f1 += 1
            n_arch += 1
            step(
                "evaluate",
                id=cand.id,
                level="architecture",
                fidelity="F1",
                status=cand.status,
                area_um2=cand.qor.area_um2,
                cost_s=cand.cost_s,
            )
            time_candidate(cand, reason=f"F3 after extract {name} — reorder remaining")

    while n_f1 < _f1_room() and time.time() < t_end:
        logic_focus = _logic_cone_focus(plan, attr, design_id=design_id)
        knobs = propose_logic_boils(mem, focus=logic_focus)
        if knobs is None:
            extra = next(
                (
                    p
                    for p in propose_from_attr(mem, focus=logic_focus, attr=attr)
                    if p.get("level") == "logic"
                    and knobs_fp("logic", {k: p[k] for k in ("name", "abc_args", "abc_ops", "abc_script") if k in p})
                    not in mem.seen_knobs("logic")
                ),
                None,
            )
            if extra:
                knobs = {
                    "name": extra.get("name"),
                    "abc_args": list(extra.get("abc_args") or []),
                    "abc_ops": list(extra.get("abc_ops") or []),
                    "abc_script": "file",
                    "via": extra.get("via"),
                }
            else:
                step("stop", reason="logic space exhausted at this budget")
                break
        if knobs is None:
            break
        knobs = stamp_cone_knobs(knobs, logic_focus)
        pred = predict_f1_area(mem.by_level("logic"), list(knobs.get("abc_ops") or []))
        best = _best_area(mem, "logic")
        acq = knobs.get("acq") or {}
        pred_wns = None
        if acq.get("mu_wns") is not None:
            pred_wns = {"mean": acq.get("mu_wns"), "std": acq.get("std_wns")}
        pay, why = should_pay_f1(pred, best, pred_wns, baseline_wns(mem))
        step("propose", level="logic", knobs=knobs, fidelity="F1", pred=pred, pay=pay, why=why)
        if not pay:
            mem.add(
                Candidate(
                    id=DesignMemory.new_id(),
                    design_id=design_id,
                    parent_id=phys.id if phys else None,
                    level="logic",
                    knobs=knobs,
                    knobs_fp=knobs_fp("logic", knobs),
                    rtl_fp=None,
                    netlist_fp=None,
                    fidelity="F0",
                    qor=QoR(fidelity="F0", note=why),
                    cost_s=0.0,
                    pred=pred,
                    status="skip",
                    note=why,
                )
            )
            continue
        if time.time() + estimated_cost_s(mem, "F1", design_id, cost_key="F1") > t_end and n_f1:
            step("stop", reason="budget would not cover another F1")
            break
        cand = evaluate_f1_abc(
            rtl=rtl,
            liberty=lib,
            knobs=knobs,
            mem=mem,
            design_id=design_id,
            parent_id=phys.id if phys else None,
            level="logic",
            top=top,
        )
        cand.pred = residual(cand.qor.area_um2, pred) or pred
        if attr.get("status") == "READY":
            cand.attr = {
                "inherited_from": "physical_ir",
                "scope": focus.get("scope"),
                "modules": focus.get("modules"),
                "transform": knobs.get("name"),
                "note": "F1 does not re-solve IR; attribution is context from F4",
            }
        mem.touch(cand)
        n_f1 += 1
        step(
            "evaluate",
            id=cand.id,
            level="logic",
            fidelity="F1",
            status=cand.status,
            area_um2=cand.qor.area_um2,
            cost_s=cand.cost_s,
        )
        time_candidate(cand, reason="F3 after ABC so EHVI sees WNS")

    n_ctrl = sum(
        1
        for c in mem.by_level("logic")
        if c.status == "ok" and c.fidelity == "F1" and (c.knobs or {}).get("cone") == "ctrl"
    )
    pay_ctrl, why_ctrl = (
        should_pay_ctrl_cone(mem, budget_left=t_end - time.time(), attr=attr, n_ctrl=n_ctrl)
        if spec.has_cone("ctrl")
        else (False, "design has no FSM cone — not inventing GCD ctrl")
    )
    step("acquire", fidelity="F1_CTRL_CONE", pay=pay_ctrl, why=why_ctrl)
    if spec.has_cone("ctrl") and pay_ctrl and time.time() < t_end:
        knobs = propose_logic_boils(mem, focus="ctrl") or {
            "name": "boils_rewrite_balance",
            "abc_args": [],
            "abc_ops": ["rewrite", "balance"],
            "abc_script": "file",
        }
        knobs = stamp_cone_knobs(knobs, "ctrl")
        if knobs_fp("logic", knobs) not in mem.seen_knobs("logic"):
            step("propose", level="logic", knobs=knobs, fidelity="F1", why=why_ctrl)
            cand = evaluate_f1_abc(
                rtl=rtl,
                liberty=lib,
                knobs=knobs,
                mem=mem,
                design_id=design_id,
                parent_id=phys.id if phys else None,
                level="logic",
                top=top,
            )
            cand.attr = {
                "inherited_from": "sta_path",
                "scope": "logic_cone",
                "modules": ["ctrl"],
                "transform": knobs.get("name"),
                "cone": "ctrl",
                "note": "ctrl-cone ABC; not leftover of dpath, not a chip restart",
            }
            mem.touch(cand)
            step(
                "evaluate",
                id=cand.id,
                level="logic",
                fidelity="F1",
                status=cand.status,
                area_um2=cand.qor.area_um2,
                cost_s=cand.cost_s,
                via="ctrl_cone",
                reason="attributed-ctrl-cone-abc",
            )
            time_candidate(cand, reason="F3 after ctrl-cone ABC")

    from .planner import pred_costs

    _stage_ctx = {
        "mem": mem,
        "plan": plan,
        "t_end": t_end,
        "step": step,
        "design_id": design_id,
        "rtl": rtl,
        "liberty": lib,
        "top": top,
        "ensure_mapped_netlist": ensure_mapped_netlist,
        "mapped_pick": _mapped_pick,
        "f1_ok": f1_ok,
        "f1_pareto_parents": f1_pareto_parents,
        "f1_area_winner": f1_area_winner,
        "f1_wns_winner": f1_wns_winner,
        "flowlab_params": flowlab_params,
        "gpl_density": gpl_density,
        "phys": phys,
        "attr": attr,
        "time_candidate": time_candidate,
        "f1_max": f1_max,
        "max_shots": dict(max_shots or {}),
        "pred_by_id": pred_costs(mem),
        "variant": variant,
        "admit_paid_f4": admit_paid_f4,
        "evaluate_f4_extract": evaluate_f4_extract,
        "evaluate_f4_pdn": evaluate_f4_pdn,
        "evaluate_f4_scale": evaluate_f4_scale,
        "evaluate_f4_static_mesh": evaluate_f4_static_mesh,
        "evaluate_f4_static_straps": evaluate_f4_static_straps,
        "evaluate_f4_em_straps": evaluate_f4_em_straps,
        "evaluate_host_arrivals": evaluate_host_arrivals,
        "GOLD_KNOBS": GOLD_KNOBS,
        "latest_ok_extract": latest_ok_extract,
        "latest_ok_host_extract": latest_ok_host_extract,
        "latest_host_arrivals": latest_host_arrivals,
        "latest_host_extract_cand": latest_host_extract_cand,
        "iscale_host": iscale_host,
        "timing_of": timing_of,
        "next_pdn_spec": next_pdn_spec,
        "persist_hotspot_join": persist_hotspot_join,
    }
    for _stage in STAGES_LOGIC_TRANSFORM:
        run_stage(_stage, _stage_ctx)

    # F2-fast on the best F1 netlists (logic + architecture winners).
    # GRT sits BETWEEN F3 STA and F3 SDF — order is data in STAGES_PLACE_ROUTE.
    for _stage in STAGES_PLACE_ROUTE:
        run_stage(_stage, _stage_ctx)

    # residual / F5-port / port_steer / catalog / f2_region — order is data.
    for _stage in STAGES_STEER_GAP:
        run_stage(_stage, _stage_ctx)

    for _stage in STAGES_F4_HEAD:
        run_stage(_stage, _stage_ctx)

    for _stage in STAGES_IR_STEER:
        run_stage(_stage, _stage_ctx)

    for _stage in STAGES_IR_CELL:
        run_stage(_stage, _stage_ctx)

    for _stage in STAGES_IR_CHAMP:
        run_stage(_stage, _stage_ctx)

    for _stage in STAGES_IR_INSPECT:
        run_stage(_stage, _stage_ctx)

    for _stage in STAGES_IR_REGION_CELL:
        run_stage(_stage, _stage_ctx)

    # Depth ≥ 1 of the refine chain is a generic action queue. Depth 0
    # (winning_ir_region_cell size-up / extract / PDN) stays above; leftover
    # leftover leftover leftover is not a new block — next_stage returns None
    # when the leftover is empty and the unused catalog is exhausted.
    plan_levels = {s["level"] for s in plan["steps"]}
    while time.time() < t_end:
        paid = run_next_refine(
            mem,
            budget_left=t_end - time.time(),
            plan_levels=plan_levels,
            design_id=design_id,
            variant=variant,
            rtl=rtl,
            liberty=lib,
            step=step,
            t_end=t_end,
            ensure_mapped_netlist=ensure_mapped_netlist,
            evaluate_cell_size=evaluate_cell_size,
            evaluate_f4_extract=evaluate_f4_extract,
            evaluate_f4_pdn=evaluate_f4_pdn,
            extract_on_disk=extract_on_disk,
            persist_hotspot_join=persist_hotspot_join,
            flowlab_params=flowlab_params,
            gpl_density=gpl_density,
            winning_host_pdn=winning_host_pdn,
        )
        if not paid:
            break

    for _stage in STAGES_IR_SOLVERS:
        run_stage(_stage, _stage_ctx)

    synth_f0 = propose_synthesis_f0(mem, design_id, current_abc_area=flowlab_params().get("abcArea"))
    for c in synth_f0:
        step("propose", level="synthesis", knobs=c.knobs, fidelity="F0")

    front = {
        lv: pareto_front((c.id, c.qor) for c in mem.by_level(lv) if c.status == "ok")
        for lv in LEVELS
    }
    pred = predict_f1_area(mem.by_level("logic"))
    pred_by_id: dict[str, float] = {}
    for c in mem.all():
        p = c.pred if isinstance(c.pred, dict) else None
        if not p:
            continue
        for k in ("area_um2", "wns_cost", "dynamic_ir_mv"):
            if p.get(k) is not None:
                pred_by_id[c.id] = float(p[k])
                break
    front_gated = {
        lv: next_candidate_ids(mem, lv, pred=pred_by_id or None)
        for lv in LEVELS
    }
    f4s = predict_f4_from_f1(mem.all())
    win_static = winning_static_pdn(mem)
    win_em = winning_em_pdn(mem)
    report = {
        "ok": True,
        "kind": "dse",
        "engine": "studio-dse",
        "variant": variant,
        "design_id": design_id,
        "architecture": [
            "layered search: architecture ≠ logic ≠ synthesis ≠ physical ≠ routing ≠ PDN",
            "F0 SSK-GP area + RUDY-class congestion; not IR",
            "F1 chip flatten-first (area teacher 409.108) · cone-local ABC on dpath and on ctrl when STA names the FSM",
            "synthesis F1 = ORFS abc_speed.script (ABC_AREA=0); abc_area stays F0-only; not abc_ops",
            "cell-local drive-up on the attributed OpenSTA worst path (module-scoped); not ABC",
            "IR-hotspot cell drive-up: I-scale-win xy → ODB inst_power_map join → module-scoped size-up — not STA path, not VCD",
            "net-local BUF on attributed worst-path hops (module-scoped); not ABC",
            "port-net BUF on attributed ctrl↔dpath hops at the parent (scope=port); not intra-module hops",
            "F2 ingest + F2-fast netgraph + budgeted GPL + catalog GPL + IR-bin region GPL + GRT",
            "F3 OpenSTA interleaved after each F1 (ideal; hier paths on cone F1) + GRT SDF + OpenRCX SPEF",
            "QoR PD axes: stdcell area, n_cells, WNS, TNS, total power, leakage; HPWL µm at F2+; internal/switching observation-only",
            "F5-lite detailed_route (2 iter, no CTS) + OpenRCX SPEF + OpenSTA read_spef — not make finish",
            "F5-CTS clock_tree_synthesis + DRT + OpenRCX + OpenSTA set_propagated_clock — not make finish",
            "F5-local OpenRCX SPEF on the cell/net netlist — F3→F5 residual, not a reused F1 SPEF",
            "F5-port OpenRCX SPEF on the port-net BUF netlist — not the intra-module net host",
            "F5-port residual steers intra-module BUF on SPEF hops — not another port BUF, not ABC",
            "active learning: F3→F5-lite residual orders cell vs net host; F3→F5-local residual + uncertainty pick the next level",
            "F4 I-scale uses F3 power of the attributed host (port-steer/port-net/net/cell), not synth-only WNS-winner",
            "F3 host arrivals: report_arrival on that same host — t50 for I(t), not extract STA, not VCD",
            "F4 host extract: write_pg_spice on the attributed netlist — not the synth F1 mesh, not gold",
            "F4 host-region extract: density cap on the host IR bin — not gold rXY on synth F1, not more ABC",
            "F4 IR residual loop: winning family on the region mesh, then unused pkg L on the candidate — not ABC, not gold",
            "F4 host IR residual loop: winning family on the host-region mesh, then unused pkg L on the unconstrained host — not candidate IR-steer",
            "F4 I-scale-win: I(t)×P of the attributed host on the winning host PDN point after host IR-steer — not the unconstrained first I-scale",
            "F4 IR-cell extract: write_pg_spice on the ODB-joined size-up — residual vs host extract, not STA-only",
            "F4 IR-cell PDN: 1× residual restamps the winning family on the sized mesh — not a flattened cell+decap vector",
            "F4 IR-cell region: seq-heavy 1× bin ≠ host bin — density cap on the sized netlist, not more combo size-up",
            "F4 IR-cell-region PDN: large spatial residual restamps the winning family on the capped mesh — not host IR-steer",
            "F4 winning-IR catalog: unused Dynamic IR (decap then pkg L, inherit host pkg_r) on a strap/EM R-graph — not pitch, not width, not host/candidate IR-steer, not gold",
            "F4 I-scale-champ: I(t)×P of the IR-cell host on winning_ir_pdn — not I-scale-win on the stale host-win mesh, not host arrivals",
            "F3 IR-cell-champ: I-scale-champ xy → ODB join on the champion extract → drive-up — re-paid when winning_ir extract moves, not the first ctrl IR-cell, not STA path",
            "F4 IR-cell-champ extract: write_pg_spice on the champ-sized netlist — residual vs IR-cell extract; re-paid per champ extract, not host",
            "F4 IR-cell-champ PDN: 1× residual restamps the winning family on that sized mesh — re-paid on a new champ extract, not host IR-steer",
            "F3 IR-cell-champ-cone: leftover cells on the champ-extract join (minus champ size-up) → drive-up on the champ-sized netlist — not first ctrl, not STA path",
            "F4 IR-cell-champ-cone extract: write_pg_spice on the leftover-cone netlist — residual vs IR-cell-champ extract; re-paid per champ extract, not host",
            "F4 IR-cell-champ-cone PDN: 1× residual restamps the winning family on that leftover-cone mesh — re-paid on a new cone extract, not champ IR-steer",
            "F4 IR-cell-champ-cone-region: leftover-cone 1× bin ≠ champ extract and seq-heavy — density cap on the leftover-cone netlist; re-paid when the residual hotspot leaves the capped bin, not more combo size-up, not IR-cell-region rXY",
            "F4 IR-cell-champ-cone-region PDN: |Δ| ≥ 1 mV restamps the winning family on that capped leftover mesh — re-paid on a new cone extract, not champ IR-steer",
            "F4 leftover-cone-region loop: inspect → density cap → |Δ| PDN → residual hotspot → next bin, up to 4 shots — not one-pass, not a flattened region vector",
            "F4 winning-IR-region: winning-IR 1× bin ≠ leftover-cone / IR-cell-region and seq-heavy — density cap on the IR-cell netlist; re-paid when the residual hotspot leaves the capped bin, not leftover-cone rXY, not more combo size-up, not IR-cell-region rXY, not gold rXY",
            "F4 winning-IR-region PDN: |Δ| ≥ 1 mV restamps the winning family on that capped winning-IR mesh — re-paid on a new region extract, not leftover-cone-region PDN, not champ IR-steer",
            "F4 winning-IR-region loop: inspect → density cap → |Δ| PDN → residual hotspot → next bin ≠ IR-cell-region, up to 4 shots — not one-pass, not leftover-cone rXY, not a flattened region vector",
            "F3 winning-IR-region-cell: leftover combo cells on the region PDN join (minus IR-cell / champ / leftover-cone) — drive-up on the IR-cell netlist, not leftover-cone flatten, not more density cap",
            "F4 winning-IR-region-cell extract: write_pg_spice on that leftover-combo netlist — residual vs the winning-IR-region extract; re-paid per region extract, not leftover-cone",
            "F4 winning-IR-region-cell PDN: 1× residual restamps the winning family on that leftover-combo mesh — re-paid on a new cell extract, not leftover-cone PDN, not champ IR-steer",
            "F3 winning-IR-region-cell leftover: leftover combo cells on the leftover-combo PDN join (minus leftover-combo / IR-cell / champ / leftover-cone) — drive-up on the leftover-combo netlist, not leftover-combo flatten, not leftover-cone, not more density cap",
            "F4 winning-IR-region-cell leftover extract: write_pg_spice on that leftover netlist — residual vs the leftover-combo extract; re-paid per cell extract, not leftover-cone",
            "F4 winning-IR-region-cell leftover PDN: 1× residual restamps the winning family on that leftover mesh — re-paid on a new leftover extract, not leftover-combo PDN, not leftover-cone PDN, not champ IR-steer",
            "F3 leftover leftover leftover: leftover leftover leftover cells on the leftover leftover PDN join (minus leftover leftover / leftover-combo / IR-cell / champ / leftover-cone) — drive-up on the leftover leftover netlist, not leftover leftover flatten, not leftover-combo, not leftover-cone, not more density cap",
            "F4 leftover leftover leftover extract: write_pg_spice on that leftover leftover leftover netlist — residual vs the leftover leftover extract; re-paid per leftover leftover extract, not leftover-combo",
            "F4 leftover leftover leftover PDN: 1× residual restamps the winning family on that leftover leftover leftover mesh — re-paid on a new leftover leftover leftover extract, not leftover leftover PDN, not leftover-combo PDN, not leftover-cone PDN, not champ IR-steer",
            "F4 leftover leftover leftover catalog: unused Dynamic IR (C then L, inherit leftover leftover leftover PDN pkg_r) on the leftover leftover leftover extract after winning family — not winning_ir catalog, not leftover leftover leftover leftover combo size-up, not pitch, not gold",
            "F4 AMG/RAS/Krylov-champ: MF solver residual on winning_ir_pdn with the same DirectLU knobs — re-paid when the 1× extract moves (strap mesh), not candidate AMG, not gold",
            "F4 static IR: winning_static_pdn is a separate 1× ranking; unused pkg_r (DC ohmic) — decap/pkg L do not move static, not Dynamic IR-steer",
            "F4 static mesh: null pkg_r residual (ideal bump V) pays denser bumps on the champ ODB — same place, not a new GPL, not gold",
            "F4 static straps: null bump residual (same n_v on this die) pays denser metal4 on the champ ODB — pdngen -ripup, not bumps, not gold",
            "F4 EM width: after strap pitch, unused metal4 width searches J=I/(wt) on the same place — same-mesh residual vs strap J, mixed-mesh vs EM champ, not pitch, not decap, not gold",
            "F4 ingest gold + candidate write_pg_spice + OpenSTA arrivals + DirectLU/AMG/RAS/Krylov + static IR",
            "IR combo on dpath → cone extracts then cone-local ABC; ctrl hops → ctrl-cone ABC, not leftover of dpath",
            "hierarchy chip→block→region→cone→cell→net; IR rXY → OpenROAD density cap on that bin → optional extract",
            "Pareto per level — EHVI acquires, it does not replace the front",
            "BOiLS EHVI(area,WNS[+IR]) · DRiLLS UCB+IR · GNN HPWL · AutoDMP GPL · MF PDN AMG/RAS/Krylov residual",
        ],
        "not": [
            "flattened black-box of all knobs",
            "neural voltage map as sign-off",
            "make finish launched from the controller (F5-lite and F5-CTS are not signoff)",
            "LLM as the optimizer (proposer-only; DSE_LLM_URL optional)",
            "signal SPEF C mapped onto the PDN extract",
        ],
        "layers": adapter_status(),
        "budget_s": budget_s,
        "spent_s": sum(c.cost_s for c in mem.all()),
        "n_candidates": len(mem),
        "n_f1": sum(1 for c in mem.all() if c.fidelity == "F1"),
        "n_f1_synth": sum(1 for c in mem.by_level("synthesis") if c.fidelity == "F1"),
        "n_ctrl_cone": sum(
            1
            for c in mem.by_level("logic")
            if c.status == "ok" and c.fidelity == "F1" and (c.knobs or {}).get("cone") == "ctrl"
        ),
        "n_dpath_cone": sum(
            1
            for c in mem.by_level("logic")
            if c.status == "ok" and c.fidelity == "F1" and (c.knobs or {}).get("cone") == "dpath"
        ),
        "n_cell": sum(
            1 for c in mem.by_level("cell") if (c.knobs or {}).get("source") == "cell_size_up" and c.status == "ok"
        ),
        "n_ir_cell": sum(
            1 for c in mem.by_level("cell") if (c.knobs or {}).get("source") == "cell_size_ir" and c.status == "ok"
        ),
        "n_ir_cell_champ": sum(
            1
            for c in mem.by_level("cell")
            if (c.knobs or {}).get("source") == "cell_size_ir_champ" and c.status == "ok"
        ),
        "ir_cell_champ_wns_ns": next(
            (
                float((c.artifacts or {}).get("wns_ns"))
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "cell_size_ir_champ"
                and (c.artifacts or {}).get("wns_ns") is not None
            ),
            None,
        ),
        "ir_cell_champ_modules": next(
            (
                ",".join(
                    dict.fromkeys(
                        str(x).split("/")[0]
                        for x in (c.knobs or {}).get("cells") or []
                        if "/" in str(x)
                    )
                )
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_champ"
            ),
            None,
        ),
        "n_f4_ir_cell_champ_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_ir_cell_champ_extract" and c.status == "ok"
        ),
        "ir_cell_champ_extract_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_champ_extract"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_champ_extract_residual_mv": next(
            (
                float((c.attr or {}).get("residual_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_champ_extract"
                and (c.attr or {}).get("residual_mv") is not None
            ),
            None,
        ),
        "n_ir_cell_champ_pdn": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_ir_cell_champ_pdn" and c.status == "ok"
        ),
        "ir_cell_champ_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_ir_cell_champ_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_champ_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_ir_cell_champ_pdn"
            ),
            None,
        ),
        "ir_cell_champ_pdn_vs_host_win_mv": next(
            (
                float((c.attr or {}).get("residual_vs_host_win_mv"))
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_ir_cell_champ_pdn"
                and (c.attr or {}).get("residual_vs_host_win_mv") is not None
            ),
            None,
        ),
        "n_ir_cell_champ_cone": sum(
            1
            for c in mem.by_level("cell")
            if (c.knobs or {}).get("source") == "cell_size_ir_champ_cone" and c.status == "ok"
        ),
        "ir_cell_champ_cone_wns_ns": next(
            (
                float((c.artifacts or {}).get("wns_ns"))
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "cell_size_ir_champ_cone"
                and (c.artifacts or {}).get("wns_ns") is not None
            ),
            None,
        ),
        "ir_cell_champ_cone_modules": next(
            (
                ",".join(
                    dict.fromkeys(
                        str(x).split("/")[0]
                        for x in (c.knobs or {}).get("cells") or []
                        if "/" in str(x)
                    )
                )
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_champ_cone"
            ),
            None,
        ),
        "n_f4_ir_cell_champ_cone_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_extract" and c.status == "ok"
        ),
        "ir_cell_champ_cone_extract_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_extract"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_champ_cone_extract_residual_mv": next(
            (
                float((c.attr or {}).get("residual_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_extract"
                and (c.attr or {}).get("residual_mv") is not None
            ),
            None,
        ),
        "n_ir_cell_champ_cone_pdn": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_pdn" and c.status == "ok"
        ),
        "ir_cell_champ_cone_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_champ_cone_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_pdn"
            ),
            None,
        ),
        "ir_cell_champ_cone_pdn_vs_host_win_mv": next(
            (
                float((c.attr or {}).get("residual_vs_host_win_mv"))
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_pdn"
                and (c.attr or {}).get("residual_vs_host_win_mv") is not None
            ),
            None,
        ),
        "n_f4_ir_cell_champ_cone_region_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract" and c.status == "ok"
        ),
        "ir_cell_champ_cone_region_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_champ_cone_region_residual_mv": next(
            (
                float((c.attr or {}).get("residual_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract"
                and (c.attr or {}).get("residual_mv") is not None
            ),
            None,
        ),
        "ir_cell_champ_cone_region_bin": next(
            (
                str((c.knobs or {}).get("region") or (c.artifacts or {}).get("region_bin") or "")
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract"
            ),
            None,
        ),
        "n_ir_cell_champ_cone_region_pdn": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_region_pdn" and c.status == "ok"
        ),
        "ir_cell_champ_cone_region_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_region_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_champ_cone_region_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_region_pdn"
            ),
            None,
        ),
        "ir_cell_champ_cone_region_pdn_vs_host_win_mv": next(
            (
                float((c.attr or {}).get("residual_vs_host_win_mv"))
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_region_pdn"
                and (c.attr or {}).get("residual_vs_host_win_mv") is not None
            ),
            None,
        ),
        "n_f4_winning_ir_region_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_winning_ir_region_extract" and c.status == "ok"
        ),
        "winning_ir_region_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_winning_ir_region_extract"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_region_residual_mv": next(
            (
                float((c.attr or {}).get("residual_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_winning_ir_region_extract"
                and (c.attr or {}).get("residual_mv") is not None
            ),
            None,
        ),
        "winning_ir_region_bin": next(
            (
                str((c.knobs or {}).get("region") or (c.artifacts or {}).get("region_bin") or "")
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_extract"
            ),
            None,
        ),
        "n_winning_ir_region_pdn": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_winning_ir_region_pdn" and c.status == "ok"
        ),
        "winning_ir_region_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_region_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_region_pdn"
            ),
            None,
        ),
        "winning_ir_region_pdn_vs_host_win_mv": next(
            (
                float((c.attr or {}).get("residual_vs_host_win_mv"))
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_pdn"
                and (c.attr or {}).get("residual_vs_host_win_mv") is not None
            ),
            None,
        ),
        "n_winning_ir_region_cell": sum(
            1
            for c in mem.by_level("cell")
            if (c.knobs or {}).get("source") == "cell_size_ir_winning_region" and c.status == "ok"
        ),
        "winning_ir_region_cell_wns_ns": next(
            (
                float((c.artifacts or {}).get("wns_ns"))
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "cell_size_ir_winning_region"
                and (c.artifacts or {}).get("wns_ns") is not None
            ),
            None,
        ),
        "winning_ir_region_cell_modules": next(
            (
                ",".join(
                    dict.fromkeys(
                        str(x).split("/")[0]
                        for x in (c.knobs or {}).get("cells") or []
                        if "/" in str(x)
                    )
                )
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_winning_region"
            ),
            None,
        ),
        "n_f4_winning_ir_region_cell_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_extract" and c.status == "ok"
        ),
        "winning_ir_region_cell_extract_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_extract"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_region_cell_extract_residual_mv": next(
            (
                float((c.attr or {}).get("residual_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_extract"
                and (c.attr or {}).get("residual_mv") is not None
            ),
            None,
        ),
        "n_winning_ir_region_cell_pdn": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_pdn" and c.status == "ok"
        ),
        "winning_ir_region_cell_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_region_cell_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_pdn"
            ),
            None,
        ),
        "winning_ir_region_cell_pdn_vs_host_win_mv": next(
            (
                float((c.attr or {}).get("residual_vs_host_win_mv"))
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_pdn"
                and (c.attr or {}).get("residual_vs_host_win_mv") is not None
            ),
            None,
        ),
        "n_winning_ir_region_cell_leftover": sum(
            1
            for c in mem.by_level("cell")
            if (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover" and c.status == "ok"
        ),
        "winning_ir_region_cell_leftover_wns_ns": next(
            (
                float((c.artifacts or {}).get("wns_ns"))
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover"
                and (c.artifacts or {}).get("wns_ns") is not None
            ),
            None,
        ),
        "winning_ir_region_cell_leftover_modules": next(
            (
                ",".join(
                    dict.fromkeys(
                        str(x).split("/")[0]
                        for x in (c.knobs or {}).get("cells") or []
                        if "/" in str(x)
                    )
                )
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover"
            ),
            None,
        ),
        "n_f4_winning_ir_region_cell_leftover_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover_extract" and c.status == "ok"
        ),
        "winning_ir_region_cell_leftover_extract_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover_extract"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_region_cell_leftover_extract_residual_mv": next(
            (
                float((c.attr or {}).get("residual_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover_extract"
                and (c.attr or {}).get("residual_mv") is not None
            ),
            None,
        ),
        "n_winning_ir_region_cell_leftover_pdn": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover_pdn" and c.status == "ok"
        ),
        "winning_ir_region_cell_leftover_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_region_cell_leftover_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover_pdn"
            ),
            None,
        ),
        "winning_ir_region_cell_leftover_pdn_vs_host_win_mv": next(
            (
                float((c.attr or {}).get("residual_vs_host_win_mv"))
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover_pdn"
                and (c.attr or {}).get("residual_vs_host_win_mv") is not None
            ),
            None,
        ),
        "n_winning_ir_region_cell_leftover2": sum(
            1
            for c in mem.by_level("cell")
            if (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover2" and c.status == "ok"
        ),
        "winning_ir_region_cell_leftover2_wns_ns": next(
            (
                float((c.artifacts or {}).get("wns_ns"))
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover2"
                and (c.artifacts or {}).get("wns_ns") is not None
            ),
            None,
        ),
        "winning_ir_region_cell_leftover2_modules": next(
            (
                ",".join(
                    dict.fromkeys(
                        str(x).split("/")[0]
                        for x in (c.knobs or {}).get("cells") or []
                        if "/" in str(x)
                    )
                )
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover2"
            ),
            None,
        ),
        "n_f4_winning_ir_region_cell_leftover2_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover2_extract" and c.status == "ok"
        ),
        "winning_ir_region_cell_leftover2_extract_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover2_extract"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_region_cell_leftover2_extract_residual_mv": next(
            (
                float((c.attr or {}).get("residual_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover2_extract"
                and (c.attr or {}).get("residual_mv") is not None
            ),
            None,
        ),
        "n_winning_ir_region_cell_leftover2_pdn": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover2_pdn" and c.status == "ok"
        ),
        "winning_ir_region_cell_leftover2_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover2_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_region_cell_leftover2_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover2_pdn"
            ),
            None,
        ),
        "winning_ir_region_cell_leftover2_pdn_vs_host_win_mv": next(
            (
                float((c.attr or {}).get("residual_vs_host_win_mv"))
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover2_pdn"
                and (c.attr or {}).get("residual_vs_host_win_mv") is not None
            ),
            None,
        ),
        "n_winning_ir_region_cell_leftover2_catalog": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover2_catalog" and c.status == "ok"
        ),
        "winning_ir_region_cell_leftover2_catalog_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover2_catalog"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_region_cell_leftover2_catalog_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover2_catalog"
            ),
            None,
        ),
        "winning_ir_region_cell_leftover2_catalog_vs_pdn_mv": next(
            (
                float((c.attr or {}).get("residual_vs_leftover2_pdn_mv"))
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover2_catalog"
                and (c.attr or {}).get("residual_vs_leftover2_pdn_mv") is not None
            ),
            None,
        ),
        "refine": _refine_report(mem),
        "n_f4_amg_champ": sum(
            1
            for c in mem.by_level("pdn")
            if (c.attr or {}).get("via") == "f4_solver_amg_champ" and c.status == "ok"
        ),
        "ir_champ_amg_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "f4_solver_amg_champ"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_champ_amg_vs_direct_mv": next(
            (
                float((c.attr or {}).get("residual_vs_direct_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "f4_solver_amg_champ"
                and (c.attr or {}).get("residual_vs_direct_mv") is not None
            ),
            None,
        ),
        "n_f4_ras_champ": sum(
            1
            for c in mem.by_level("pdn")
            if (c.attr or {}).get("via") == "f4_solver_ras_champ" and c.status == "ok"
        ),
        "ir_champ_ras_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "f4_solver_ras_champ"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_champ_ras_vs_direct_mv": next(
            (
                float((c.attr or {}).get("residual_vs_direct_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "f4_solver_ras_champ"
                and (c.attr or {}).get("residual_vs_direct_mv") is not None
            ),
            None,
        ),
        "n_f4_krylov_champ": sum(
            1
            for c in mem.by_level("pdn")
            if (c.attr or {}).get("via") == "f4_solver_krylov_champ" and c.status == "ok"
        ),
        "ir_champ_krylov_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "f4_solver_krylov_champ"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_champ_krylov_vs_direct_mv": next(
            (
                float((c.attr or {}).get("residual_vs_direct_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "f4_solver_krylov_champ"
                and (c.attr or {}).get("residual_vs_direct_mv") is not None
            ),
            None,
        ),
        "winning_static_mv": (
            float(win_static.qor.static_ir_mv)
            if win_static is not None and win_static.qor.static_ir_mv is not None
            else None
        ),
        "winning_static_id": (win_static.id if win_static is not None else None),
        "winning_static_extract": (
            str((win_static.knobs or {}).get("extract_id") or win_static.id)
            if win_static is not None
            else None
        ),
        "n_static_ir_steer": sum(
            1
            for c in mem.by_level("pdn")
            if (c.attr or {}).get("via") == "active_f4_static_ir" and c.status == "ok"
        ),
        "static_ir_steer_mv": next(
            (
                float(c.qor.static_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_static_ir"
                and c.qor.static_ir_mv is not None
            ),
            None,
        ),
        "static_ir_steer_dyn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_static_ir"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "static_ir_steer_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_static_ir"
            ),
            None,
        ),
        "n_static_mesh": sum(
            1
            for c in mem.by_level("pdn")
            if (c.attr or {}).get("via") == "active_f4_static_mesh" and c.status == "ok"
        ),
        "static_mesh_mv": next(
            (
                float(c.qor.static_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_static_mesh"
                and c.qor.static_ir_mv is not None
            ),
            None,
        ),
        "static_mesh_dyn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_static_mesh"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "static_mesh_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_static_mesh"
            ),
            None,
        ),
        "static_mesh_vs_champ_mv": next(
            (
                float((c.attr or {}).get("residual_vs_static_champ_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_static_mesh"
                and (c.attr or {}).get("residual_vs_static_champ_mv") is not None
            ),
            None,
        ),
        "n_static_straps": sum(
            1
            for c in mem.by_level("pdn")
            if (c.attr or {}).get("via") == "active_f4_static_straps" and c.status == "ok"
        ),
        "static_straps_mv": next(
            (
                float(c.qor.static_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_static_straps"
                and c.qor.static_ir_mv is not None
            ),
            None,
        ),
        "static_straps_dyn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_static_straps"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "static_straps_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_static_straps"
            ),
            None,
        ),
        "static_straps_vs_champ_mv": next(
            (
                float((c.attr or {}).get("residual_vs_static_champ_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_static_straps"
                and (c.attr or {}).get("residual_vs_static_champ_mv") is not None
            ),
            None,
        ),
        "static_straps_n_r": next(
            (
                (c.artifacts or {}).get("n_r")
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_static_straps"
            ),
            None,
        ),
        "winning_em_j": (
            float(win_em.qor.em_j_a_m2)
            if win_em is not None and win_em.qor.em_j_a_m2 is not None
            else None
        ),
        "winning_em_id": (win_em.id if win_em is not None else None),
        "n_em_straps": sum(
            1
            for c in mem.by_level("pdn")
            if (c.attr or {}).get("via") == "active_f4_em_straps" and c.status == "ok"
        ),
        "em_straps_j": next(
            (
                float(c.qor.em_j_a_m2)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_em_straps"
                and c.qor.em_j_a_m2 is not None
            ),
            None,
        ),
        "em_straps_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_em_straps"
            ),
            None,
        ),
        "n_winning_ir_pdn": sum(
            1
            for c in mem.by_level("pdn")
            if (c.attr or {}).get("via") == "active_f4_winning_ir_pdn" and c.status == "ok"
        ),
        "winning_ir_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "winning_ir_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_pdn"
            ),
            None,
        ),
        "winning_ir_pdn_vs_champ_mv": next(
            (
                float((c.attr or {}).get("residual_vs_winning_ir_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_winning_ir_pdn"
                and (c.attr or {}).get("residual_vs_winning_ir_mv") is not None
            ),
            None,
        ),
        "em_straps_vs_champ_j": next(
            (
                float((c.attr or {}).get("residual_vs_em_champ_j"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_em_straps"
                and (c.attr or {}).get("residual_vs_em_champ_j") is not None
            ),
            None,
        ),
        "em_straps_vs_strap_j": next(
            (
                float((c.attr or {}).get("residual_vs_strap_j"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_em_straps"
                and (c.attr or {}).get("residual_vs_strap_j") is not None
            ),
            None,
        ),
        "em_straps_static_mv": next(
            (
                float(c.qor.static_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_em_straps"
                and c.qor.static_ir_mv is not None
            ),
            None,
        ),
        "static_ir_steer_vs_champ_mv": next(
            (
                float((c.attr or {}).get("residual_vs_static_champ_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_static_ir"
                and (c.attr or {}).get("residual_vs_static_champ_mv") is not None
            ),
            None,
        ),
        "n_f4_ir_cell_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_ir_cell_extract" and c.status == "ok"
        ),
        "n_ir_cell_pdn": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_ir_cell_pdn" and c.status == "ok"
        ),
        "ir_cell_extract_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_extract"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_extract_residual_mv": next(
            (
                float((c.attr or {}).get("residual_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_extract"
                and (c.attr or {}).get("residual_mv") is not None
            ),
            None,
        ),
        "ir_cell_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_ir_cell_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_ir_cell_pdn"
            ),
            None,
        ),
        "n_f4_ir_cell_region_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_ir_cell_region_extract" and c.status == "ok"
        ),
        "ir_cell_region_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_region_extract"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_region_residual_mv": next(
            (
                float((c.attr or {}).get("residual_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_ir_cell_region_extract"
                and (c.attr or {}).get("residual_mv") is not None
            ),
            None,
        ),
        "ir_cell_region_bin": next(
            (
                str((c.knobs or {}).get("region") or (c.attr or {}).get("region") or "")
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_region_extract"
            ),
            None,
        ),
        "n_ir_cell_region_pdn": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_ir_cell_region_pdn" and c.status == "ok"
        ),
        "ir_cell_region_pdn_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_ir_cell_region_pdn"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_region_pdn_name": next(
            (
                str((c.knobs or {}).get("name") or "")
                for c in reversed(list(mem.all()))
                if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_ir_cell_region_pdn"
            ),
            None,
        ),
        "ir_cell_region_pdn_vs_host_win_mv": next(
            (
                float((c.attr or {}).get("residual_vs_host_win_mv"))
                for c in reversed(list(mem.all()))
                if c.status == "ok"
                and (c.attr or {}).get("via") == "active_f4_ir_cell_region_pdn"
                and (c.attr or {}).get("residual_vs_host_win_mv") is not None
            ),
            None,
        ),
        "n_f4_iscale_champ": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_iscale_champ" and c.status == "ok"
        ),
        "ir_cell_iscale_champ_mv": next(
            (
                float(c.qor.dynamic_ir_mv)
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_iscale_champ"
                and c.qor.dynamic_ir_mv is not None
            ),
            None,
        ),
        "ir_cell_iscale_champ_scale": next(
            (
                float((c.knobs or {}).get("i_scale"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_iscale_champ"
                and (c.knobs or {}).get("i_scale") is not None
            ),
            None,
        ),
        "ir_cell_iscale_champ_vs_win_mv": next(
            (
                float((c.attr or {}).get("residual_vs_iscale_win_mv"))
                for c in reversed(list(mem.by_level("pdn")))
                if c.status == "ok"
                and (c.knobs or {}).get("source") == "f4_iscale_champ"
                and (c.attr or {}).get("residual_vs_iscale_win_mv") is not None
            ),
            None,
        ),
        "n_net": sum(
            1 for c in mem.by_level("net") if (c.knobs or {}).get("source") == "net_buffer" and c.status == "ok"
        ),
        "n_net_port": sum(
            1
            for c in mem.by_level("net")
            if (c.knobs or {}).get("source") == "net_buffer_port" and c.status == "ok"
        ),
        "n_port_steer": sum(
            1 for c in mem.all() if (c.attr or {}).get("via") == "active_f5_port" and c.status == "ok"
        ),
        "n_arch": sum(1 for c in mem.by_level("architecture") if c.fidelity == "F1"),
        "n_f2_fast": sum(
            1
            for c in mem.by_level("physical")
            if c.knobs.get("source") in ("f2_fast_netgraph", "f2_fast_barycenter")
        ),
        "n_f2_gpl": sum(
            1
            for c in mem.by_level("physical")
            if c.knobs.get("source") == "f2_openroad_gpl"
        ),
        "n_f2_gpl_catalog": sum(
            1
            for c in mem.by_level("physical")
            if (c.knobs or {}).get("catalog")
        ),
        "n_f2_region": sum(
            1
            for c in mem.by_level("physical")
            if (c.knobs or {}).get("source") == "f2_openroad_gpl_region" and c.status == "ok"
        ),
        "n_f3": sum(1 for c in mem.all() if c.fidelity == "F3"),
        "n_f3_sdf": sum(
            1
            for c in mem.all()
            if (c.knobs or {}).get("source") == "f3_opensta_sdf_grt" and c.status == "ok"
        ),
        "n_f3_spef": sum(
            1
            for c in mem.all()
            if (c.knobs or {}).get("source") == "f3_opensta_spef" and c.status == "ok"
        ),
        "n_f5": sum(
            1
            for c in mem.by_level("routing")
            if (c.knobs or {}).get("source") == "f5_openroad_drt_rcx" and c.status == "ok"
        ),
        "n_f5_cts": sum(
            1
            for c in mem.by_level("routing")
            if (c.knobs or {}).get("source") == "f5_openroad_cts_rcx" and c.status == "ok"
        ),
        "n_f5_local": sum(
            1
            for c in mem.by_level("routing")
            if (c.knobs or {}).get("source") == "f5_openroad_local" and c.status == "ok"
        ),
        "n_f5_port": sum(
            1
            for c in mem.by_level("routing")
            if (c.knobs or {}).get("source") == "f5_openroad_local"
            and (c.knobs or {}).get("host_level") == "port"
            and c.status == "ok"
        ),
        "n_residual_steer": sum(
            1 for c in mem.all() if (c.attr or {}).get("via") == "active_residual" and c.status == "ok"
        ),
        "n_ir_steer": sum(
            1 for c in mem.all() if (c.attr or {}).get("via") == "active_f4_ir" and c.status == "ok"
        ),
        "n_host_ir_steer": sum(
            1
            for c in mem.all()
            if (c.attr or {}).get("via") == "active_f4_host_ir" and c.status == "ok"
        ),
        "n_f2_grt": sum(
            1
            for c in mem.by_level("routing")
            if c.knobs.get("source") == "f2_openroad_grt"
        ),
        "n_f4": sum(1 for c in mem.by_level("pdn") if c.fidelity == "F4"),
        "n_f4_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_candidate_extract" and c.status == "ok"
        ),
        "n_f4_host_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_host_extract" and c.status == "ok"
        ),
        "n_f4_host_region_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_host_region_extract" and c.status == "ok"
        ),
        "n_f4_region_extract": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_region_extract" and c.status == "ok"
        ),
        "n_f4_amg": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_solver_amg" and c.status == "ok"
        ),
        "n_f4_ras": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_solver_ras" and c.status == "ok"
        ),
        "n_f4_krylov": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_solver_krylov" and c.status == "ok"
        ),
        "n_f4_iscale": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_iscale" and c.status == "ok"
        ),
        "n_f4_iscale_win": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_iscale_win" and c.status == "ok"
        ),
        "n_host_arrivals": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") == "f4_host_arrivals" and c.status == "ok"
        ),
        "n_f4_solve": sum(
            1
            for c in mem.by_level("pdn")
            if str((c.knobs or {}).get("source") or "")
            in {
                "f4_solver_a",
                "f4_iscale",
                "f4_iscale_win",
                "f4_iscale_champ",
                "f4_candidate_extract",
                "f4_host_extract",
                "f4_host_region_extract",
                "f4_ir_cell_extract",
                "f4_ir_cell_region_extract",
                "f4_ir_cell_champ_extract",
                "f4_ir_cell_champ_cone_extract",
                "f4_ir_cell_champ_cone_region_extract",
                "f4_winning_ir_region_extract",
                "f4_winning_ir_region_cell_extract",
                "f4_winning_ir_region_cell_leftover_extract",
                "f4_winning_ir_region_cell_leftover2_extract",
                "f4_region_extract",
                "f4_solver_amg",
                "f4_solver_ras",
                "f4_solver_krylov",
            }
            or (
                str((c.knobs or {}).get("source") or "").startswith("f4_winning_ir_region_cell")
                and str((c.knobs or {}).get("source") or "").endswith("_extract")
            )
        ),
        "memory": str(mem_path),
        "surrogate_f0": pred,
        "surrogate_f1_to_f2": predict_f2_from_f1(mem.all()),
        "surrogate_f1_to_f2_gnn": predict_f2_gnn(mem.all()),
        "surrogate_f1_to_gpl": predict_gpl_from_f1(mem.all()),
        "surrogate_f1_to_wns": predict_wns_from_f1(mem.all()),
        "surrogate_f1_to_power": predict_power_from_f1(mem.all()),
        "surrogate_f1_to_f4": f4s,
        "surrogate_f1_to_f5": predict_f5_from_f1(mem.all()),
        "surrogate_f1_to_f5_cts": predict_f5_cts_from_f1(mem.all()),
        "surrogate_f3_to_f5_lite": residual_f3_to_f5_lite(mem.all()),
        "surrogate_f3_to_f5_local": residual_f3_to_f5_local(mem.all()),
        "surrogate_f4_mesh": residual_f4_mesh(mem.all()),
        "surrogate_f4_knob": residual_f4_knob(mem.all()),
        "surrogate_f4_region": residual_f4_region(mem.all()),
        "surrogate_f4_host_region": residual_f4_host_region(mem.all()),
        "surrogate_f4_static": residual_f4_static(mem.all()),
        "surrogate_f4_static_mesh": residual_f4_static_mesh(mem.all()),
        "surrogate_f4_static_straps": residual_f4_static_straps(mem.all()),
        "surrogate_f4_em": residual_f4_em(mem.all()),
        "plan": plan,
        "attribution": attr,
        "focus": focus,
        "pareto": {
            **front,
            "note": "frontiers are per level; do not rank ABC area against IR droop",
        },
        "pareto_gated": {
            **front_gated,
            "note": "timing/power gated by fidelity; pred is tie-break only",
        },
        **ir_run_labels(
            {"worst_droop_mv": win_ir.qor.dynamic_ir_mv}
            if (win_ir := winning_ir_pdn(mem)) is not None and win_ir.qor.dynamic_ir_mv is not None
            else None
        ),
        "candidates": [c.to_dict() for c in mem.all()],
        "log": log,
        "summary": _summary(
            mem,
            front.get("logic") or [],
            attr,
            sum(1 for c in mem.all() if c.fidelity == "F1"),
            sum(1 for c in mem.by_level("architecture") if c.fidelity == "F1"),
        ),
        "catalog": [s["name"] for s in CATALOG],
    }
    out = reports_dir(variant) / f"dse_{variant}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    report["report"] = str(out)
    return report


def _best_area(mem: DesignMemory, level: str) -> float | None:
    xs = [
        float(c.qor.area_um2)
        for c in mem.by_level(level)
        if c.status == "ok" and c.qor.area_um2 is not None
    ]
    return min(xs) if xs else None


def _attach_delta(cand, mem: DesignMemory) -> None:
    """Stamp attr.delta_vs_baseline (vs liberty_default). Does not touch Candidate.delta (vs parent)."""
    base = next(
        (
            c
            for c in mem.by_level("logic")
            if c.status == "ok" and c.knobs.get("name") == "liberty_default" and c.qor.area_um2
        ),
        None,
    )
    if base and cand.qor.area_um2 is not None:
        cand.attr = dict(cand.attr or {})
        cand.attr["delta_vs_baseline"] = {
            **qor_delta(cand.qor, base.qor),
            "vs": base.id,
            "note": "transform+context → Δarea vs liberty_default (same chip, different RTL extract)",
        }


def _summary(mem: DesignMemory, front_logic: list[str], attr: dict, n_f1: int, n_arch: int) -> str:
    areas = [
        (c.level, c.knobs.get("name"), c.qor.area_um2)
        for c in mem.all()
        if c.status == "ok" and c.qor.area_um2 is not None and c.fidelity == "F1"
    ]
    areas.sort(key=lambda t: t[2])
    best = f"{areas[0][0]}/{areas[0][1]} {areas[0][2]:.3f} µm²" if areas else "no F1"
    ir = ""
    for c in mem.by_level("pdn"):
        if c.status != "ok" or c.qor.dynamic_ir_mv is None:
            continue
        src = (c.knobs or {}).get("source")
        if src == "f4_region_extract" and not ir:
            ir = (
                f" · F4 region extract {c.qor.dynamic_ir_mv:.3f} mV "
                f"bin={(c.artifacts or {}).get('region_bin')} n_r={(c.artifacts or {}).get('n_r')} (not gold)"
            )
        if src == "f4_host_region_extract":
            ir = (
                f" · F4 host-region extract {c.qor.dynamic_ir_mv:.3f} mV "
                f"bin={(c.artifacts or {}).get('region_bin') or (c.knobs or {}).get('region')} "
                f"n_r={(c.artifacts or {}).get('n_r')} (not gold)"
            )
        if src == "f4_host_extract" and "host-region" not in ir:
            ir = (
                f" · F4 host extract {c.qor.dynamic_ir_mv:.3f} mV "
                f"n_r={(c.artifacts or {}).get('n_r')} (not gold)"
            )
        elif src == "f4_candidate_extract" and "host extract" not in ir and "host-region" not in ir:
            ir = (
                f" · F4 candidate extract {c.qor.dynamic_ir_mv:.3f} mV "
                f"n_r={(c.artifacts or {}).get('n_r')} (not gold)"
            )
        if src == "ingest_pdn" and not ir:
            ir = f" · F4 ingest {c.qor.dynamic_ir_mv:.3f} mV (gold teacher, unrestamped)"
    ras = ""
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.knobs or {}).get("source") != "f4_solver_ras" or c.qor.dynamic_ir_mv is None:
            continue
        if (c.attr or {}).get("via") == "f4_solver_ras_champ":
            continue
        ras = f" · RAS residual {c.qor.dynamic_ir_mv:.3f} mV (not gold)"
        break
    kry = ""
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.knobs or {}).get("source") != "f4_solver_krylov" or c.qor.dynamic_ir_mv is None:
            continue
        if (c.attr or {}).get("via") == "f4_solver_krylov_champ":
            continue
        kry = f" · Krylov/MOR residual {c.qor.dynamic_ir_mv:.3f} mV m={(c.artifacts or {}).get('m')} (not gold)"
        break
    amgc = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.attr or {}).get("via") == "f4_solver_amg_champ" and c.qor.dynamic_ir_mv is not None:
            res = (c.attr or {}).get("residual_vs_direct_mv")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            amgc = f" · AMG-champ {c.qor.dynamic_ir_mv:.3f} mV{extra} (not gold)"
            break
    rasc = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.attr or {}).get("via") == "f4_solver_ras_champ" and c.qor.dynamic_ir_mv is not None:
            res = (c.attr or {}).get("residual_vs_direct_mv")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            rasc = f" · RAS-champ {c.qor.dynamic_ir_mv:.3f} mV{extra} (not gold)"
            break
    kryc = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.attr or {}).get("via") == "f4_solver_krylov_champ" and c.qor.dynamic_ir_mv is not None:
            res = (c.attr or {}).get("residual_vs_direct_mv")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            m = (c.artifacts or {}).get("m")
            kryc = f" · Krylov-champ {c.qor.dynamic_ir_mv:.3f} mV{extra} m={m} (not gold)"
            break
    sir = ""
    win_s = winning_static_pdn(mem)
    if win_s is not None and win_s.qor.static_ir_mv is not None:
        sir = f" · static-IR champ {win_s.qor.static_ir_mv:.3f} mV"
    sir_bits: list[str] = []
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_static_ir":
            continue
        smv = c.qor.static_ir_mv
        cat = (c.knobs or {}).get("name")
        vs = (c.attr or {}).get("residual_vs_static_champ_mv")
        extra = f" Δ={float(vs):+.3f}" if vs is not None else ""
        sir_bits.append(
            f"{cat} {float(smv):.3f} mV{extra}" if smv is not None else str(cat)
        )
    if sir_bits:
        sir += " · static-IR " + "; ".join(sir_bits) + " (not gold)"
    sm_bits: list[str] = []
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_static_mesh":
            continue
        smv = c.qor.static_ir_mv
        cat = (c.knobs or {}).get("name")
        vs = (c.attr or {}).get("residual_vs_static_champ_mv")
        extra = f" Δ={float(vs):+.3f}" if vs is not None else ""
        sm_bits.append(
            f"{cat} {float(smv):.3f} mV{extra}" if smv is not None else str(cat)
        )
    if sm_bits:
        sir += " · static-mesh " + "; ".join(sm_bits) + " (not gold)"
    st_bits: list[str] = []
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_static_straps":
            continue
        smv = c.qor.static_ir_mv
        cat = (c.knobs or {}).get("name")
        vs = (c.attr or {}).get("residual_vs_static_champ_mv")
        extra = f" Δ={float(vs):+.3f}" if vs is not None else ""
        st_bits.append(
            f"{cat} {float(smv):.3f} mV{extra}" if smv is not None else str(cat)
        )
    if st_bits:
        sir += " · static-straps " + "; ".join(st_bits) + " (not gold)"
    em_bits: list[str] = []
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_em_straps":
            continue
        ej = c.qor.em_j_a_m2
        cat = (c.knobs or {}).get("name")
        vs = (c.attr or {}).get("residual_vs_em_champ_j")
        vs_s = (c.attr or {}).get("residual_vs_strap_j")
        extra = ""
        if vs_s is not None:
            extra += f" ΔJstrap={float(vs_s):+.3e}"
        if vs is not None:
            extra += f" ΔJchamp={float(vs):+.3e}"
        em_bits.append(
            f"{cat} {float(ej):.3e} A/m²{extra}" if ej is not None else str(cat)
        )
    if em_bits:
        sir += " · EM-width " + "; ".join(em_bits) + " (not gold)"
    wir_bits: list[str] = []
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_winning_ir_pdn":
            continue
        dmv = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        vs = (c.attr or {}).get("residual_vs_winning_ir_mv")
        extra = f" Δ={float(vs):+.3f}" if vs is not None else ""
        wir_bits.append(
            f"{cat} {float(dmv):.3f} mV{extra}" if dmv is not None else str(cat)
        )
    if wir_bits:
        sir += " · winning-IR catalog " + "; ".join(wir_bits) + " (not gold)"
    ctrlc = ""
    for c in mem.by_level("logic"):
        if c.status == "ok" and c.fidelity == "F1" and (c.knobs or {}).get("cone") == "ctrl" and c.qor.area_um2 is not None:
            ctrlc = f" · ctrl-cone {c.knobs.get('name')} {c.qor.area_um2:.3f} µm²"
            break
    synth = ""
    for c in mem.by_level("synthesis"):
        if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None:
            synth = f" · synth abc_speed {c.qor.area_um2:.3f} µm²"
            break
    cell = ""
    for c in mem.by_level("cell"):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_up":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            cell = f" · cell size-up n={nch} WNS={w:+.3f} ns" if w is not None else f" · cell size-up n={nch}"
            break
    ircell = ""
    for c in mem.by_level("cell"):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            # Knobs cells are the ODB join (ctrl). Inherited STA attr.modules
            # still lists the dpath path and must not steal the label.
            mods = ",".join(
                dict.fromkeys(
                    str(x).split("/")[0]
                    for x in (c.knobs or {}).get("cells") or []
                    if "/" in str(x)
                )
            ) or ",".join((c.attr or {}).get("modules") or [])
            ircell = (
                f" · IR-cell size-up n={nch} {mods} WNS={w:+.3f} ns"
                if w is not None
                else f" · IR-cell size-up n={nch} {mods}"
            )
            break
    ircchamp = ""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_champ":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            mods = ",".join(
                dict.fromkeys(
                    str(x).split("/")[0]
                    for x in (c.knobs or {}).get("cells") or []
                    if "/" in str(x)
                )
            )
            ircchamp = (
                f" · IR-cell-champ size-up n={nch} {mods} WNS={w:+.3f} ns"
                if w is not None
                else f" · IR-cell-champ size-up n={nch} {mods}"
            )
            break
    icccone = ""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_champ_cone":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            mods = ",".join(
                dict.fromkeys(
                    str(x).split("/")[0]
                    for x in (c.knobs or {}).get("cells") or []
                    if "/" in str(x)
                )
            )
            icccone = (
                f" · IR-cell-champ-cone size-up n={nch} {mods} WNS={w:+.3f} ns"
                if w is not None
                else f" · IR-cell-champ-cone size-up n={nch} {mods}"
            )
            break
    iccext = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_champ_extract":
            w = c.qor.dynamic_ir_mv
            res = (c.attr or {}).get("residual_mv")
            nr = (c.artifacts or {}).get("n_r")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            iccext = (
                f" · IR-cell-champ extract {float(w):.3f} mV{extra} n_r={nr} (not gold)"
                if w is not None
                else f" · IR-cell-champ extract n_r={nr} (not gold)"
            )
            break
    icccext = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_extract":
            w = c.qor.dynamic_ir_mv
            res = (c.attr or {}).get("residual_mv")
            nr = (c.artifacts or {}).get("n_r")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            icccext = (
                f" · IR-cell-champ-cone extract {float(w):.3f} mV{extra} n_r={nr} (not gold)"
                if w is not None
                else f" · IR-cell-champ-cone extract n_r={nr} (not gold)"
            )
            break
    iccpdn = ""
    iccp_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_ir_cell_champ_pdn":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_host_win_mv")
        extra = f" vs host-win {float(vs):+.3f}" if vs is not None else ""
        iccp_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV{extra}" if w is not None else str(cat)
        )
    if iccp_bits:
        iccpdn = " · IR-cell-champ-PDN " + "; ".join(iccp_bits)
    icccpdn = ""
    icccp_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_ir_cell_champ_cone_pdn":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_host_win_mv")
        extra = f" vs host-win {float(vs):+.3f}" if vs is not None else ""
        icccp_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV{extra}" if w is not None else str(cat)
        )
    if icccp_bits:
        icccpdn = " · IR-cell-champ-cone-PDN " + "; ".join(icccp_bits)
    icccreg = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract":
            w = c.qor.dynamic_ir_mv
            res = (c.attr or {}).get("residual_mv")
            bin_id = (c.knobs or {}).get("region") or (c.artifacts or {}).get("region_bin")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            icccreg = (
                f" · IR-cell-champ-cone-region {float(w):.3f} mV{extra} bin={bin_id} (not gold)"
                if w is not None
                else f" · IR-cell-champ-cone-region bin={bin_id} (not gold)"
            )
            break
    icccrpdn = ""
    icccrp_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_ir_cell_champ_cone_region_pdn":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_host_win_mv")
        extra = f" vs host-win {float(vs):+.3f}" if vs is not None else ""
        icccrp_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV{extra}" if w is not None else str(cat)
        )
    if icccrp_bits:
        icccrpdn = " · IR-cell-champ-cone-region-PDN " + "; ".join(icccrp_bits)
    wirreg = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_extract":
            w = c.qor.dynamic_ir_mv
            res = (c.attr or {}).get("residual_mv")
            bin_id = (c.knobs or {}).get("region") or (c.artifacts or {}).get("region_bin")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            wirreg = (
                f" · winning-IR-region {float(w):.3f} mV{extra} bin={bin_id} (not gold)"
                if w is not None
                else f" · winning-IR-region bin={bin_id} (not gold)"
            )
            break
    wirpdn = ""
    wirp_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_winning_ir_region_pdn":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_host_win_mv")
        extra = f" vs host-win {float(vs):+.3f}" if vs is not None else ""
        wirp_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV{extra}" if w is not None else str(cat)
        )
    if wirp_bits:
        wirpdn = " · winning-IR-region-PDN " + "; ".join(wirp_bits)
    wircell = ""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_winning_region":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            mods = ",".join(
                dict.fromkeys(
                    str(x).split("/")[0]
                    for x in (c.knobs or {}).get("cells") or []
                    if "/" in str(x)
                )
            )
            wircell = (
                f" · winning-IR-region-cell size-up n={nch} {mods} WNS={w:+.3f} ns"
                if w is not None
                else f" · winning-IR-region-cell size-up n={nch} {mods}"
            )
            break
    wircext = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_extract":
            w = c.qor.dynamic_ir_mv
            res = (c.attr or {}).get("residual_mv")
            nr = (c.artifacts or {}).get("n_r")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            wircext = (
                f" · winning-IR-region-cell extract {float(w):.3f} mV{extra} n_r={nr} (not gold)"
                if w is not None
                else f" · winning-IR-region-cell extract n_r={nr} (not gold)"
            )
            break
    wircpdn = ""
    wircp_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_winning_ir_region_cell_pdn":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_host_win_mv")
        extra = f" vs host-win {float(vs):+.3f}" if vs is not None else ""
        wircp_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV{extra}" if w is not None else str(cat)
        )
    if wircp_bits:
        wircpdn = " · winning-IR-region-cell-PDN " + "; ".join(wircp_bits)
    wircl = ""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            mods = ",".join(
                dict.fromkeys(
                    str(x).split("/")[0]
                    for x in (c.knobs or {}).get("cells") or []
                    if "/" in str(x)
                )
            )
            wircl = (
                f" · winning-IR-region leftover leftover size-up n={nch} {mods} WNS={w:+.3f} ns"
                if w is not None
                else f" · winning-IR-region leftover leftover size-up n={nch} {mods}"
            )
            break
    wirclext = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover_extract":
            w = c.qor.dynamic_ir_mv
            res = (c.attr or {}).get("residual_mv")
            nr = (c.artifacts or {}).get("n_r")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            wirclext = (
                f" · winning-IR-region leftover leftover extract {float(w):.3f} mV{extra} n_r={nr} (not gold)"
                if w is not None
                else f" · winning-IR-region leftover leftover extract n_r={nr} (not gold)"
            )
            break
    wirclpdn = ""
    wirclp_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_winning_ir_region_cell_leftover_pdn":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_host_win_mv")
        extra = f" vs host-win {float(vs):+.3f}" if vs is not None else ""
        wirclp_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV{extra}" if w is not None else str(cat)
        )
    if wirclp_bits:
        wirclpdn = " · winning-IR-region leftover leftover-PDN " + "; ".join(wirclp_bits)
    wircl2 = ""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover2":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            mods = ",".join(
                dict.fromkeys(
                    str(x).split("/")[0]
                    for x in (c.knobs or {}).get("cells") or []
                    if "/" in str(x)
                )
            )
            wircl2 = (
                f" · leftover leftover leftover size-up n={nch} {mods} WNS={w:+.3f} ns"
                if w is not None
                else f" · leftover leftover leftover size-up n={nch} {mods}"
            )
            break
    wircl2ext = ""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover2_extract":
            w = c.qor.dynamic_ir_mv
            res = (c.attr or {}).get("residual_mv")
            nr = (c.artifacts or {}).get("n_r")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            wircl2ext = (
                f" · leftover leftover leftover extract {float(w):.3f} mV{extra} n_r={nr} (not gold)"
                if w is not None
                else f" · leftover leftover leftover extract n_r={nr} (not gold)"
            )
            break
    wircl2pdn = ""
    wircl2p_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_winning_ir_region_cell_leftover2_pdn":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_host_win_mv")
        extra = f" vs host-win {float(vs):+.3f}" if vs is not None else ""
        wircl2p_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV{extra}" if w is not None else str(cat)
        )
    if wircl2p_bits:
        wircl2pdn = " · leftover leftover leftover-PDN " + "; ".join(wircl2p_bits)
    wircl2cat = ""
    wircl2c_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_winning_ir_region_cell_leftover2_catalog":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_leftover2_pdn_mv")
        extra = f" vs leftover leftover leftover-PDN {float(vs):+.3f}" if vs is not None else ""
        wircl2c_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV{extra}" if w is not None else str(cat)
        )
    if wircl2c_bits:
        wircl2cat = " · leftover leftover leftover-catalog " + "; ".join(wircl2c_bits)
    ircext = ""
    for c in mem.by_level("pdn"):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_extract":
            w = c.qor.dynamic_ir_mv
            res = (c.attr or {}).get("residual_mv")
            nr = (c.artifacts or {}).get("n_r")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            ircext = (
                f" · IR-cell extract {float(w):.3f} mV{extra} n_r={nr} (not gold)"
                if w is not None
                else f" · IR-cell extract n_r={nr} (not gold)"
            )
            break
    icpdn = ""
    icp_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_ir_cell_pdn":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        icp_bits.append(f"{cat} on {eid} {float(w):.3f} mV" if w is not None else str(cat))
    if icp_bits:
        icpdn = " · IR-cell-PDN " + "; ".join(icp_bits)
    icreg = ""
    for c in mem.by_level("pdn"):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_region_extract":
            w = c.qor.dynamic_ir_mv
            res = (c.attr or {}).get("residual_mv")
            bin_id = (c.knobs or {}).get("region") or (c.artifacts or {}).get("region_bin")
            extra = f" Δ={float(res):+.3f}" if res is not None else ""
            icreg = (
                f" · IR-cell-region {float(w):.3f} mV{extra} bin={bin_id} (not gold)"
                if w is not None
                else f" · IR-cell-region bin={bin_id} (not gold)"
            )
            break
    icrpdn = ""
    icrp_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_ir_cell_region_pdn":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_host_win_mv")
        extra = f" vs host-win {float(vs):+.3f}" if vs is not None else ""
        icrp_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV{extra}" if w is not None else str(cat)
        )
    if icrp_bits:
        icrpdn = " · IR-cell-region-PDN " + "; ".join(icrp_bits)
    netb = ""
    for c in mem.by_level("net"):
        if c.status == "ok" and (c.knobs or {}).get("source") == "net_buffer":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            netb = f" · net BUF n={nch} WNS={w:+.3f} ns" if w is not None else f" · net BUF n={nch}"
            break
    netp = ""
    for c in mem.by_level("net"):
        if c.status == "ok" and (c.knobs or {}).get("source") == "net_buffer_port":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            netp = f" · port-net BUF n={nch} WNS={w:+.3f} ns" if w is not None else f" · port-net BUF n={nch}"
            break
    psteer = ""
    for c in mem.by_level("net"):
        if c.status == "ok" and (c.attr or {}).get("via") == "active_f5_port":
            w = (c.artifacts or {}).get("wns_ns")
            nch = (c.artifacts or {}).get("n_changed")
            psteer = (
                f" · port-steer BUF n={nch} WNS={w:+.3f} ns"
                if w is not None
                else f" · port-steer BUF n={nch}"
            )
            break
    wns = ""
    timed = [
        (c.knobs.get("parent_name") or c.knobs.get("name"), c.qor.wns_cost)
        for c in mem.all()
        if (
            c.status == "ok"
            and c.qor.wns_cost is not None
            and c.fidelity == "F3"
            and (c.knobs or {}).get("source") == "f3_opensta_ideal"
        )
    ]
    if timed:
        timed.sort(key=lambda t: t[1])
        wns = f" · best ideal WNS {-timed[0][1]:+.3f} ns ({timed[0][0]})"
    f5 = ""
    for c in mem.all():
        if c.status != "ok" or (c.knobs or {}).get("source") != "f5_openroad_drt_rcx":
            continue
        w = (c.artifacts or {}).get("wns_ns")
        if w is not None:
            f5 = f" · F5 SPEF WNS {float(w):+.3f} ns"
            break
    f5cts = ""
    for c in mem.all():
        if c.status != "ok" or (c.knobs or {}).get("source") != "f5_openroad_cts_rcx":
            continue
        w = (c.artifacts or {}).get("wns_ns")
        ncb = (c.artifacts or {}).get("n_clkbuf")
        if w is not None:
            f5cts = f" · F5-CTS SPEF WNS {float(w):+.3f} ns (propagated, n_clkbuf={ncb})"
            break
    f5loc = ""
    f5port = ""
    for c in mem.all():
        if c.status != "ok" or (c.knobs or {}).get("source") != "f5_openroad_local":
            continue
        w = (c.artifacts or {}).get("wns_ns")
        if w is None:
            continue
        ideal = (c.artifacts or {}).get("ideal_wns_ns")
        host = (c.knobs or {}).get("host_level")
        extra = f" vs ideal {float(ideal):+.3f}" if ideal is not None else ""
        if host == "port" and not f5port:
            f5port = f" · F5-port SPEF WNS {float(w):+.3f} ns{extra}"
        elif host != "port" and not f5loc:
            f5loc = f" · F5-local SPEF WNS {float(w):+.3f} ns ({host}{extra})"
    steers = ""
    for c in mem.all():
        if c.status == "ok" and (c.attr or {}).get("via") == "active_residual":
            steers = f" · residual-steer {c.level}"
            break
    irst = ""
    ir_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_ir":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        ir_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV" if w is not None else str(cat)
        )
    if ir_bits:
        irst = " · IR-steer " + "; ".join(ir_bits)
    hirst = ""
    hir_bits: list[str] = []
    for c in mem.all():
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_host_ir":
            continue
        w = c.qor.dynamic_ir_mv
        cat = (c.knobs or {}).get("name")
        eid = (c.knobs or {}).get("extract_id")
        hir_bits.append(
            f"{cat} on {eid} {float(w):.3f} mV" if w is not None else str(cat)
        )
    if hir_bits:
        hirst = " · host-IR-steer " + "; ".join(hir_bits)
    isc = ""
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.knobs or {}).get("source") != "f4_iscale":
            continue
        sc = (c.knobs or {}).get("i_scale")
        host = (c.knobs or {}).get("parent_name") or (c.knobs or {}).get("host_source")
        w = c.qor.dynamic_ir_mv
        if sc is not None and w is not None:
            via = (c.knobs or {}).get("sta_via")
            extra = f" sta={via}" if via else ""
            isc = f" · I-scale {host} ×{float(sc):.3f} {float(w):.3f} mV{extra}"
        break
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.knobs or {}).get("source") != "f4_iscale_win":
            continue
        sc = (c.knobs or {}).get("i_scale")
        host = (c.knobs or {}).get("parent_name") or (c.knobs or {}).get("host_source")
        w = c.qor.dynamic_ir_mv
        eid = (c.knobs or {}).get("extract_id")
        if sc is not None and w is not None:
            isc += (
                f" · I-scale-win {host} ×{float(sc):.3f} {float(w):.3f} mV "
                f"on {eid}"
            )
        break
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.knobs or {}).get("source") != "f4_iscale_champ":
            continue
        sc = (c.knobs or {}).get("i_scale")
        host = (c.knobs or {}).get("parent_name") or (c.knobs or {}).get("host_source")
        w = c.qor.dynamic_ir_mv
        eid = (c.knobs or {}).get("extract_id")
        vs = (c.attr or {}).get("residual_vs_iscale_win_mv")
        extra = f" vs I×w {float(vs):+.3f}" if vs is not None else ""
        if sc is not None and w is not None:
            isc += (
                f" · I-scale-champ {host} ×{float(sc):.3f} {float(w):.3f} mV "
                f"on {eid}{extra}"
            )
        break
    arrs = ""
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.knobs or {}).get("source") != "f4_host_arrivals":
            continue
        ninst = (c.artifacts or {}).get("n_inst")
        h = (c.knobs or {}).get("host_source") or (c.knobs or {}).get("parent_name")
        arrs = f" · host arrivals {h} n_inst={ninst}"
        break
    mods = ",".join(attr.get("modules") or []) or "unjoined"
    return (
        f"DSE {len(mem)} candidates · F1 {n_f1} (arch {n_arch}) · logic Pareto {len(front_logic)} · "
        f"best mapped area {best}{ctrlc}{synth}{cell}{ircell}{ircchamp}{icccone}{iccext}{icccext}{iccpdn}{icccpdn}{icccreg}{icccrpdn}{wirreg}{wirpdn}{wircell}{wircext}{wircpdn}{wircl}{wirclext}{wirclpdn}{wircl2}{wircl2ext}{wircl2pdn}{wircl2cat}{ircext}{icpdn}{icreg}{icrpdn}{amgc}{rasc}{kryc}{sir}{netb}{netp}{psteer}{wns}{f5}{f5cts}{f5loc}{f5port}{steers}{irst}{hirst}{arrs}{isc} · IR cone {mods}{ir}{ras}{kry}"
    )

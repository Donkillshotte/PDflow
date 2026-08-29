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
  pdn          — F4 ingest + candidate write_pg_spice + host extract + host-region density cap + host IR-steer + DirectLU/AMG/RAS/Krylov + I-scale of the attributed host (not gold)

Acquisition ≈ expected improvement + information − compute − extrapolation risk.
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path

from .abc_space import CATALOG
from .acquire import (
    latest_ok_extract,
    latest_ok_host_extract,
    latest_host_arrivals,
    should_pay_host_arrivals,
    should_pay_f4_host_extract,
    should_pay_f4_host_region,
    latest_host_extract_cand,
    should_pay_f2_fast,
    should_pay_f2_gpl,
    should_pay_f2_region,
    should_pay_f2_grt,
    should_pay_f3_sdf,
    should_pay_f3_spef,
    should_pay_f3_sta,
    should_pay_cell_size,
    should_pay_ir_cell,
    should_pay_ctrl_cone,
    should_pay_net_buffer,
    should_pay_net_port,
    _attributed_cross_module_nets,
    should_pay_f1_synth,
    should_pay_f4_amg,
    should_pay_f4_extract,
    should_pay_f4_krylov,
    should_pay_f4_ras,
    should_pay_f4_region_extract,
    should_pay_f5_cts,
    should_pay_f5_drt,
    should_pay_f5_local,
    should_pay_f5_port,
    should_pay_port_steer,
    latest_port_host,
    should_pay_residual_steer,
    should_pay_ir_steer,
    should_pay_host_ir_steer,
    extract_on_disk,
    local_hosts,
    should_pay_f4_pdn,
    should_pay_f4_scale,
    should_pay_f4_scale_win,
    should_pay_physical_catalog,
)
from .active import (
    iscale_host,
    iscale_parent,
    winning_host_pdn,
    ir_hotspot_cells,
    order_local_hosts,
    steer_from_ir_residual,
    steer_from_host_ir_residual,
    steer_from_port_residual,
    steer_from_residual,
)
from .arch_space import emit_gcd_variant, stamp_cone_knobs
from .attribute import attribute_from_path, local_scope
from .boils import propose_logic_boils, should_pay_f1
from .fidelity import (
    COST_HINT,
    evaluate_cell_size,
    evaluate_net_buffer,
    evaluate_net_port_buffer,
    evaluate_f1_abc,
    evaluate_f1_synth,
    evaluate_f2_fast,
    evaluate_f2_gpl,
    evaluate_f2_grt,
    evaluate_f3_sdf,
    evaluate_f3_spef,
    evaluate_f3_sta,
    evaluate_f5_cts,
    evaluate_f5_drt,
    evaluate_f5_local,
    evaluate_f4_extract,
    evaluate_f4_pdn,
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
from .fingerprint import knobs_fp
from .layers import adapter_status
from .netgraph import is_gate_cell_netlist
from .memory import Candidate, DesignMemory
from .metrics import QoR, pareto_front
from .mo import baseline_wns, timing_of
from .pdn_space import GOLD_KNOBS, next_pdn_spec
from .physical_space import gpl_density, next_catalog_spec, propose_physical_f0, propose_synthesis_f0
from .planner import plan_search, rank_extracts
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
    residual,
)

LEVELS = ("architecture", "logic", "synthesis", "cell", "net", "physical", "routing", "pdn")


def propose_logic(mem: DesignMemory, focus: str = "chip") -> dict | None:
    """Public hook used by tests: a logic proposal never carries physical knobs."""
    return propose_logic_boils(mem, focus=focus)


def _logic_cone_focus(plan: dict, attr: dict) -> str:
    """Prefer dpath cone ABC when both modules are on the path. Ctrl is a later shot."""
    mods = list(attr.get("modules") or [])
    focus = str(plan.get("focus") or "chip")
    if "dpath" in mods or focus == "dpath":
        return "dpath"
    if "ctrl" in mods or focus == "ctrl":
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


def _mapped_pick(cands, *, rtl, liberty):
    for cand in cands:
        if cand is None:
            continue
        w = ensure_mapped_netlist(cand, rtl=rtl, liberty=liberty)
        mapped = (w.artifacts or {}).get("mapped_v")
        if mapped and is_gate_cell_netlist(Path(mapped)):
            return w
    return None


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
) -> dict:
    t_end = time.time() + max(float(budget_s), 1.0)
    root = Path(__file__).resolve().parents[1].parent
    rtl = Path(rtl) if rtl else root / "learn" / "flowlab" / "gcd.v"
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

    def time_candidate(cand, *, reason: str):
        """Interleave F3 so WNS can steer the next extract / ABC sequence."""
        if cand is None or cand.status != "ok":
            return None
        if time.time() + COST_HINT["F3"] > t_end:
            return None
        n_have = sum(
            1
            for c in mem.all()
            if (c.knobs or {}).get("source") == "f3_opensta_ideal" and c.status == "ok"
        )
        if n_have >= 8:
            return None
        if any(
            (c.knobs or {}).get("source") == "f3_opensta_ideal"
            and (c.knobs or {}).get("parent_id") == cand.id
            and c.status == "ok"
            for c in mem.all()
        ):
            return None
        w = ensure_mapped_netlist(cand, rtl=rtl, liberty=lib)
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
    plan = plan_search(attr, mem, f2_cong=f2_cong)
    step("plan", **{k: plan[k] for k in ("focus", "combo_frac", "f2_cong") if k in plan})
    for s in plan["steps"]:
        step("plan_step", **s)

    def _synth_f1_done() -> bool:
        return any(c.level == "synthesis" and c.fidelity == "F1" for c in mem.all())

    def _f1_room() -> int:
        """Reserve one F1 slot for ORFS abc_speed until that layer is measured."""
        return f1_max - (0 if _synth_f1_done() else 1)

    n_f1 = 0
    n_arch = 0

    # Seed the logic baseline first so architecture ΔQoR has a teacher.
    if n_f1 < f1_max and time.time() < t_end:
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
    plan = plan_search(attr, mem, f2_cong=f2_cong)

    # Hierarchical architecture: planner orders extracts from IR attribution.
    arch_step = next((s for s in plan["steps"] if s["level"] == "architecture"), None)
    if arch_step and time.time() < t_end:
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
            if time.time() + COST_HINT["F1"] > t_end and n_f1:
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
        logic_focus = _logic_cone_focus(plan, attr)
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
        if time.time() + COST_HINT["F1"] > t_end and n_f1:
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
    pay_ctrl, why_ctrl = should_pay_ctrl_cone(
        mem, budget_left=t_end - time.time(), attr=attr, n_ctrl=n_ctrl
    )
    step("acquire", fidelity="F1_CTRL_CONE", pay=pay_ctrl, why=why_ctrl)
    if pay_ctrl and time.time() < t_end:
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

    pay_synth, why_synth = should_pay_f1_synth(
        mem, budget_left=t_end - time.time(), n_f1=n_f1, f1_max=f1_max
    )
    step("acquire", fidelity="F1_SYNTH", pay=pay_synth, why=why_synth)
    if any(s["level"] == "synthesis" for s in plan["steps"]) and pay_synth and time.time() < t_end:
        step(
            "propose",
            level="synthesis",
            knobs={"name": "orfs_abc_speed", "abcArea": 0, "source": "orfs_abc_script"},
            fidelity="F1",
            why=why_synth,
        )
        cand = evaluate_f1_synth(
            rtl=rtl,
            liberty=lib,
            mem=mem,
            design_id=design_id,
            parent_id=phys.id if phys else None,
        )
        if attr.get("status") == "READY":
            cand.attr = {
                "inherited_from": "physical_ir",
                "scope": "chip",
                "transform": "orfs_abc_speed",
                "note": "synthesis F1 is ORFS abc_speed.script; not flattened into BOiLS abc_ops",
            }
        mem.touch(cand)
        n_f1 += 1
        step(
            "evaluate",
            id=cand.id,
            level="synthesis",
            fidelity="F1",
            status=cand.status,
            area_um2=cand.qor.area_um2,
            cost_s=cand.cost_s,
            via="orfs_abc_speed",
        )
        time_candidate(cand, reason="F3 after ORFS abc_speed so WNS can compare to liberty_default")

    n_cell = sum(
        1 for c in mem.by_level("cell") if (c.knobs or {}).get("source") == "cell_size_up" and c.status == "ok"
    )
    pay_cell, why_cell = should_pay_cell_size(
        mem, budget_left=t_end - time.time(), n_cell=n_cell
    )
    step("acquire", fidelity="CELL_SIZE", pay=pay_cell, why=why_cell)
    if any(s["level"] == "cell" for s in plan["steps"]) and pay_cell and time.time() < t_end:
        pick = _mapped_pick(
            [f1_wns_winner(mem), f1_area_winner(mem)] + [c for c in f1_ok(mem)],
            rtl=rtl,
            liberty=lib,
        )
        if pick:
            mem.touch(pick)
            child = evaluate_cell_size(pick, mem, design_id=design_id)
            if child:
                step(
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

    n_net = sum(
        1 for c in mem.by_level("net") if (c.knobs or {}).get("source") == "net_buffer" and c.status == "ok"
    )
    pay_net, why_net = should_pay_net_buffer(
        mem, budget_left=t_end - time.time(), n_net=n_net
    )
    step("acquire", fidelity="NET_BUF", pay=pay_net, why=why_net)
    if any(s["level"] == "net" for s in plan["steps"]) and pay_net and time.time() < t_end:
        pick = next(
            (
                c
                for c in reversed(list(mem.by_level("cell")))
                if c.status == "ok" and (c.artifacts or {}).get("mapped_v")
            ),
            None,
        )
        if pick is None:
            pick = _mapped_pick(
                [f1_wns_winner(mem), f1_area_winner(mem)] + [c for c in f1_ok(mem)],
                rtl=rtl,
                liberty=lib,
            )
        if pick:
            mem.touch(pick)
            child = evaluate_net_buffer(pick, mem, design_id=design_id)
            if child:
                step(
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

    n_port = sum(
        1
        for c in mem.by_level("net")
        if (c.knobs or {}).get("source") == "net_buffer_port" and c.status == "ok"
    )
    pay_port, why_port = should_pay_net_port(
        mem, budget_left=t_end - time.time(), n_net=n_net, n_port=n_port
    )
    step("acquire", fidelity="NET_PORT", pay=pay_port, why=why_port)
    if any(s["level"] == "net_port" for s in plan["steps"]) and pay_port and time.time() < t_end:
        pick = None
        for cand in list(mem.by_level("net"))[::-1] + list(mem.by_level("cell"))[::-1] + [
            c for c in f1_ok(mem)
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
            pick = _mapped_pick(
                [f1_wns_winner(mem), f1_area_winner(mem)] + [c for c in f1_ok(mem)],
                rtl=rtl,
                liberty=lib,
            )
        if pick:
            mem.touch(pick)
            child = evaluate_net_port_buffer(
                pick,
                mem,
                design_id=design_id,
                hops=_attributed_cross_module_nets(mem),
            )
            if child:
                step(
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

    # F2-fast on the best F1 netlists (logic + architecture winners).
    n_f2 = 0
    pay_fast, why_fast = should_pay_f2_fast(mem, n_f2=n_f2)
    if any(s["level"] == "f2_fast" for s in plan["steps"]) and pay_fast and time.time() < t_end:
        winners = list(f1_pareto_parents(mem))
        seen = {c.id for c in winners}
        extra = [c for c in f1_ok(mem) if c.id not in seen]
        extra.sort(key=lambda c: float(c.qor.area_um2))
        winners.extend(extra)
        for w in winners:
            if n_f2 >= 4 or time.time() >= t_end:
                break
            w = ensure_mapped_netlist(w, rtl=rtl, liberty=lib)
            mem.touch(w)
            child = evaluate_f2_fast(w, mem, design_id=design_id)
            if child:
                n_f2 += 1
                step(
                    "evaluate",
                    id=child.id,
                    level="physical",
                    fidelity="F2",
                    via="f2_fast_netgraph",
                    parent=w.id,
                    hpwl=(child.artifacts or {}).get("hpwl"),
                    congestion=child.qor.congestion,
                )

    n_gpl = sum(
        1
        for c in mem.by_level("physical")
        if (c.knobs or {}).get("source") == "f2_openroad_gpl" and c.status == "ok"
    )
    pay_gpl, why_gpl = should_pay_f2_gpl(mem, budget_left=t_end - time.time(), n_gpl=n_gpl)
    step("acquire", fidelity="F2_GPL", pay=pay_gpl, why=why_gpl)
    if any(s["level"] == "f2_gpl" for s in plan["steps"]) and pay_gpl and time.time() < t_end:
        pick = _mapped_pick(
            [f1_area_winner(mem)] + [c for c in f1_ok(mem)],
            rtl=rtl,
            liberty=lib,
        )
        if pick:
            w = pick
            mem.touch(w)
            params = flowlab_params()
            util0 = float(params.get("coreUtilization") or 35.0)
            den0 = gpl_density(util0, params.get("placeDensityAddon") or 0.2)
            child = evaluate_f2_gpl(w, mem, design_id=design_id, util=util0, density=den0)
            if child:
                step(
                    "evaluate",
                    id=child.id,
                    level="physical",
                    fidelity="F2",
                    via="f2_openroad_gpl",
                    parent=w.id,
                    hpwl_um=(child.artifacts or {}).get("hpwl_um"),
                    overflow=child.qor.congestion,
                    status=child.status,
                )

    n_sta = sum(1 for c in mem.all() if (c.knobs or {}).get("source") == "f3_opensta_ideal" and c.status == "ok")
    pay_sta, why_sta = should_pay_f3_sta(mem, budget_left=t_end - time.time(), n_sta=n_sta)
    step("acquire", fidelity="F3", pay=pay_sta, why=why_sta)
    if any(s["level"] == "f3_sta" for s in plan["steps"]) and pay_sta and time.time() < t_end:
        ranked = [
            c
            for c in mem.all()
            if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None
        ]
        ranked.sort(key=lambda c: float(c.qor.area_um2))
        for w in ranked[:4]:
            if time.time() >= t_end:
                break
            w = ensure_mapped_netlist(w, rtl=rtl, liberty=lib)
            mem.touch(w)
            child = evaluate_f3_sta(w, mem, design_id=design_id)
            if child:
                step(
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

    n_grt = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f2_openroad_grt" and c.status == "ok"
    )
    pay_grt, why_grt = should_pay_f2_grt(mem, budget_left=t_end - time.time(), n_grt=n_grt)
    step("acquire", fidelity="F2_GRT", pay=pay_grt, why=why_grt)
    if any(s["level"] == "routing" for s in plan["steps"]) and pay_grt and time.time() < t_end:
        pick = _mapped_pick(
            [f1_area_winner(mem)] + [c for c in f1_ok(mem)],
            rtl=rtl,
            liberty=lib,
        )
        if pick:
            mem.touch(pick)
            child = evaluate_f2_grt(pick, mem, design_id=design_id)
            if child:
                step(
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

    n_sdf = sum(
        1
        for c in mem.all()
        if (c.knobs or {}).get("source") == "f3_opensta_sdf_grt" and c.status == "ok"
    )
    pay_sdf, why_sdf = should_pay_f3_sdf(mem, budget_left=t_end - time.time(), n_sdf=n_sdf)
    step("acquire", fidelity="F3_SDF", pay=pay_sdf, why=why_sdf)
    if any(s["level"] == "f3_sdf" for s in plan["steps"]) and pay_sdf and time.time() < t_end:
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
        if host:
            sdfc = evaluate_f3_sdf(host, mem, design_id=design_id)
            if sdfc:
                step(
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

    n_f5 = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_drt_rcx" and c.status == "ok"
    )
    pay_f5, why_f5 = should_pay_f5_drt(mem, budget_left=t_end - time.time(), n_f5=n_f5)
    step("acquire", fidelity="F5", pay=pay_f5, why=why_f5)
    if any(s["level"] == "f5_drt" for s in plan["steps"]) and pay_f5 and time.time() < t_end:
        pick = _mapped_pick(
            [f1_area_winner(mem)] + [c for c in f1_ok(mem)],
            rtl=rtl,
            liberty=lib,
        )
        if pick:
            mem.touch(pick)
            child = evaluate_f5_drt(pick, mem, design_id=design_id)
            if child:
                step(
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

    n_spef = sum(
        1 for c in mem.all() if (c.knobs or {}).get("source") == "f3_opensta_spef" and c.status == "ok"
    )
    pay_spef, why_spef = should_pay_f3_spef(mem, budget_left=t_end - time.time(), n_spef=n_spef)
    step("acquire", fidelity="F3_SPEF", pay=pay_spef, why=why_spef)
    if any(s["level"] == "f3_spef" for s in plan["steps"]) and pay_spef and time.time() < t_end:
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
        if host:
            spc = evaluate_f3_spef(host, mem, design_id=design_id)
            if spc:
                step(
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

    n_f5_cts = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_cts_rcx" and c.status == "ok"
    )
    pay_cts, why_cts = should_pay_f5_cts(mem, budget_left=t_end - time.time(), n_f5_cts=n_f5_cts)
    step("acquire", fidelity="F5_CTS", pay=pay_cts, why=why_cts)
    if any(s["level"] == "f5_cts" for s in plan["steps"]) and pay_cts and time.time() < t_end:
        pick = _mapped_pick(
            [f1_area_winner(mem)] + [c for c in f1_ok(mem)],
            rtl=rtl,
            liberty=lib,
        )
        if pick:
            mem.touch(pick)
            child = evaluate_f5_cts(pick, mem, design_id=design_id)
            if child:
                step(
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

    n_f5_local = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_local" and c.status == "ok"
    )
    pay_loc, why_loc = should_pay_f5_local(
        mem, budget_left=t_end - time.time(), n_f5_local=n_f5_local
    )
    hosts_ord, host_why = order_local_hosts(mem)
    step("acquire", fidelity="F5_LOCAL", pay=pay_loc, why=why_loc, **host_why)
    if any(s["level"] == "f5_local" for s in plan["steps"]) and pay_loc and time.time() < t_end:
        child = None
        host = None
        for cand in hosts_ord or local_hosts(mem):
            mem.touch(cand)
            child = evaluate_f5_local(cand, mem, design_id=design_id)
            host = cand
            if child and child.status == "ok":
                break
        if child:
            step(
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

    steer = steer_from_residual(mem)
    n_steer = sum(1 for c in mem.all() if (c.attr or {}).get("via") == "active_residual" and c.status == "ok")
    pay_st, why_st = should_pay_residual_steer(
        mem, budget_left=t_end - time.time(), steer=steer, n_steer=n_steer
    )
    step("acquire", fidelity="RESIDUAL_STEER", pay=pay_st, why=why_st, steer=steer)
    if any(s["level"] == "residual_steer" for s in plan["steps"]) and pay_st and steer and time.time() < t_end:
        host = mem.get(str(steer.get("host_id") or "")) if steer.get("host_id") else None
        child = None
        if steer["level"] == "f5_local" and host is not None:
            mem.touch(host)
            child = evaluate_f5_local(host, mem, design_id=design_id)
        elif steer["level"] == "cell" and host is not None:
            mem.touch(host)
            child = evaluate_cell_size(host, mem, design_id=design_id, cells=list(steer.get("cells") or []))
        elif steer["level"] == "net" and host is not None:
            mem.touch(host)
            child = evaluate_net_buffer(host, mem, design_id=design_id, hops=list(steer.get("hops") or []))
        if child:
            child.attr = dict(child.attr or {})
            child.attr["via"] = "active_residual"
            child.attr["steer"] = {k: steer[k] for k in steer if k != "cells" and k != "hops"}
            mem.touch(child)
            step(
                "evaluate",
                id=child.id,
                level=child.level,
                fidelity=child.fidelity,
                via="active_residual",
                parent=host.id if host else None,
                host_level=steer.get("host_level") or (host.level if host else None),
                residual_ns=steer.get("residual_ns"),
                wns_ns=(child.artifacts or {}).get("wns_ns"),
                status=child.status,
                reason=steer.get("reason"),
            )

    n_f5_port = sum(
        1
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_local"
        and (c.knobs or {}).get("host_level") == "port"
        and c.status == "ok"
    )
    pay_fp, why_fp = should_pay_f5_port(
        mem, budget_left=t_end - time.time(), n_f5_port=n_f5_port
    )
    step("acquire", fidelity="F5_PORT", pay=pay_fp, why=why_fp)
    if any(s["level"] == "f5_port" for s in plan["steps"]) and pay_fp and time.time() < t_end:
        host = latest_port_host(mem)
        if host:
            mem.touch(host)
            child = evaluate_f5_local(host, mem, design_id=design_id)
            if child:
                step(
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

    steer_port = steer_from_port_residual(mem)
    n_psteer = sum(
        1 for c in mem.all() if (c.attr or {}).get("via") == "active_f5_port" and c.status == "ok"
    )
    pay_ps, why_ps = should_pay_port_steer(
        mem, budget_left=t_end - time.time(), steer=steer_port, n_steer=n_psteer
    )
    step("acquire", fidelity="PORT_STEER", pay=pay_ps, why=why_ps, steer=steer_port)
    if any(s["level"] == "port_steer" for s in plan["steps"]) and pay_ps and steer_port and time.time() < t_end:
        host = mem.get(str(steer_port.get("host_id") or "")) if steer_port.get("host_id") else None
        if host is not None and steer_port.get("level") == "net":
            mem.touch(host)
            child = evaluate_net_buffer(
                host,
                mem,
                design_id=design_id,
                hops=list(steer_port.get("hops") or []),
                source="net_buffer_spef",
            )
            if child:
                child.attr = dict(child.attr or {})
                child.attr["via"] = "active_f5_port"
                child.attr["steer"] = {k: steer_port[k] for k in steer_port if k != "hops"}
                mem.touch(child)
                step(
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

    phys_f0 = propose_physical_f0(mem, design_id)
    for c in phys_f0:
        step("propose", level="physical", knobs=c.knobs, fidelity="F0")
    n_cat = sum(1 for c in mem.by_level("physical") if (c.knobs or {}).get("catalog"))
    pay_cat, why_cat = should_pay_physical_catalog(
        mem, budget_left=t_end - time.time(), n_catalog=n_cat
    )
    step("acquire", fidelity="F2_GPL_CATALOG", pay=pay_cat, why=why_cat)
    spec = next_catalog_spec(mem) if pay_cat else None
    if spec and time.time() < t_end:
        # Second GPL shot: prefer the WNS incumbent (Pareto), not the same area netlist.
        pick = _mapped_pick(
            [f1_wns_winner(mem), f1_area_winner(mem)] + [c for c in f1_ok(mem)],
            rtl=rtl,
            liberty=lib,
        )
        if pick:
            mem.touch(pick)
            util_c = float(spec["coreUtilization"])
            den_c = gpl_density(util_c, spec["placeDensityAddon"])
            child = evaluate_f2_gpl(
                pick,
                mem,
                design_id=design_id,
                util=util_c,
                density=den_c,
                extra_knobs={
                    "catalog": spec["name"],
                    "coreUtilization": spec["coreUtilization"],
                    "placeDensityAddon": spec["placeDensityAddon"],
                },
            )
            if child:
                step(
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

    n_reg = sum(
        1
        for c in mem.by_level("physical")
        if (c.knobs or {}).get("source") == "f2_openroad_gpl_region" and c.status == "ok"
    )
    pay_reg, why_reg = should_pay_f2_region(
        mem,
        budget_left=t_end - time.time(),
        n_region=n_reg,
        region=attr.get("region"),
        x_dbu=attr.get("x_dbu"),
        y_dbu=attr.get("y_dbu"),
    )
    step("acquire", fidelity="F2_REGION", pay=pay_reg, why=why_reg)
    if any(s["level"] == "f2_region" for s in plan["steps"]) and pay_reg and time.time() < t_end:
        pick = _mapped_pick(
            [f1_wns_winner(mem), f1_area_winner(mem)] + [c for c in f1_ok(mem)],
            rtl=rtl,
            liberty=lib,
        )
        if pick:
            mem.touch(pick)
            params = flowlab_params()
            util_r = float(params.get("coreUtilization") or 35.0)
            den_r = gpl_density(util_r, params.get("placeDensityAddon") or 0.2)
            child = evaluate_f2_gpl(
                pick,
                mem,
                design_id=design_id,
                util=util_r,
                density=den_r,
                extra_knobs={
                    "region": attr.get("region"),
                    "x_dbu": attr.get("x_dbu"),
                    "y_dbu": attr.get("y_dbu"),
                    "region_density": 0.30,
                },
            )
            if child:
                step(
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

    n_ext = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_candidate_extract" and c.status == "ok"
    )
    pay_ext, why_ext = should_pay_f4_extract(
        mem, budget_left=t_end - time.time(), n_extract=n_ext
    )
    step("acquire", fidelity="F4_EXTRACT", pay=pay_ext, why=why_ext)
    if any(s["level"] == "f4_extract" for s in plan["steps"]) and pay_ext and time.time() < t_end:
        prefer = []
        base_p_ext = None
        for c in mem.by_level("logic"):
            if c.status == "ok" and c.knobs.get("name") == "liberty_default":
                _w, p = timing_of(mem, c)
                if p:
                    base_p_ext = p
                    break
        if base_p_ext:
            for cand in (f1_wns_winner(mem), f1_area_winner(mem), *f1_ok(mem)):
                if cand is None:
                    continue
                _w, p = timing_of(mem, cand)
                if p is None or abs(float(p) / float(base_p_ext) - 1.0) < 0.03:
                    continue
                prefer.append(cand)
                break
        pick = _mapped_pick(
            prefer + [f1_wns_winner(mem), f1_area_winner(mem)] + [c for c in f1_ok(mem)],
            rtl=rtl,
            liberty=lib,
        )
        if pick:
            mem.touch(pick)
            params = flowlab_params()
            util_e = float(params.get("coreUtilization") or 35.0)
            den_e = gpl_density(util_e, params.get("placeDensityAddon") or 0.2)
            child = evaluate_f4_extract(
                pick,
                mem,
                design_id=design_id,
                variant=variant,
                util=util_e,
                density=den_e,
            )
            if child:
                step(
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

    n_reg_ext = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_region_extract" and c.status == "ok"
    )
    pay_rext, why_rext = should_pay_f4_region_extract(
        mem,
        budget_left=t_end - time.time(),
        n_extract=n_reg_ext,
        region=attr.get("region"),
        x_dbu=attr.get("x_dbu"),
        y_dbu=attr.get("y_dbu"),
    )
    step("acquire", fidelity="F4_REGION_EXTRACT", pay=pay_rext, why=why_rext)
    if any(s["level"] == "f4_region_extract" for s in plan["steps"]) and pay_rext and time.time() < t_end:
        pick = _mapped_pick(
            [f1_wns_winner(mem), f1_area_winner(mem)] + [c for c in f1_ok(mem)],
            rtl=rtl,
            liberty=lib,
        )
        if pick:
            mem.touch(pick)
            params = flowlab_params()
            util_e = float(params.get("coreUtilization") or 35.0)
            den_e = gpl_density(util_e, params.get("placeDensityAddon") or 0.2)
            child = evaluate_f4_extract(
                pick,
                mem,
                design_id=design_id,
                variant=variant,
                util=util_e,
                density=den_e,
                region=attr.get("region"),
                x_dbu=attr.get("x_dbu"),
                y_dbu=attr.get("y_dbu"),
                region_density=0.30,
            )
            if child:
                step(
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

    ext_hit = latest_ok_extract(mem)
    extract_id = str(ext_hit["extract_id"]) if ext_hit else "finish"
    n_pdn_f4 = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_solver_a"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "finish") == extract_id
    )
    pay_pdn, why_pdn = should_pay_f4_pdn(
        mem,
        budget_left=t_end - time.time(),
        n_pdn=n_pdn_f4,
        variant=variant,
        extract_id=extract_id,
    )
    step("acquire", fidelity="F4_PDN", pay=pay_pdn, why=why_pdn)
    spec_pdn = next_pdn_spec(mem, extract_id=extract_id) if pay_pdn else None
    if spec_pdn and time.time() < t_end:
        ingest = next(
            (c for c in mem.by_level("pdn") if (c.knobs or {}).get("source") == "ingest_pdn"),
            None,
        )
        child = evaluate_f4_pdn(
            mem,
            spec_pdn,
            variant=variant,
            design_id=design_id,
            parent_id=(ext_hit["candidate"].id if ext_hit else (ingest.id if ingest else None)),
            spice=ext_hit["spice"] if ext_hit else None,
            insts=ext_hit["insts"] if ext_hit else None,
            extract_id=extract_id,
            sta=ext_hit.get("sta") if ext_hit else None,
        )
        if child:
            step(
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

    n_amg = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_solver_amg"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "finish") == extract_id
    )
    pay_amg, why_amg = should_pay_f4_amg(
        mem,
        budget_left=t_end - time.time(),
        n_amg=n_amg,
        variant=variant,
        extract_id=extract_id,
    )
    step("acquire", fidelity="F4_AMG", pay=pay_amg, why=why_amg)
    if any(s["level"] == "f4_amg" for s in plan["steps"]) and pay_amg and time.time() < t_end:
        ingest = next(
            (c for c in mem.by_level("pdn") if (c.knobs or {}).get("source") == "ingest_pdn"),
            None,
        )
        child = evaluate_f4_pdn(
            mem,
            {"name": "amg_residual", **GOLD_KNOBS},
            variant=variant,
            design_id=design_id,
            parent_id=(ext_hit["candidate"].id if ext_hit else (ingest.id if ingest else None)),
            spice=ext_hit["spice"] if ext_hit else None,
            insts=ext_hit["insts"] if ext_hit else None,
            extract_id=extract_id,
            solver="amg",
            sta=ext_hit.get("sta") if ext_hit else None,
        )
        if child:
            step(
                "evaluate",
                id=child.id,
                level="pdn",
                fidelity="F4",
                via="f4_solver_amg",
                extract_id=extract_id,
                droop_mv=child.qor.dynamic_ir_mv,
                em_j=child.qor.em_j_a_m2,
                gold=False,
                status=child.status,
                reason="mf-amg-residual-vs-direct",
            )

    n_ras = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_solver_ras"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "finish") == extract_id
    )
    pay_ras, why_ras = should_pay_f4_ras(
        mem,
        budget_left=t_end - time.time(),
        n_ras=n_ras,
        variant=variant,
        extract_id=extract_id,
    )
    step("acquire", fidelity="F4_RAS", pay=pay_ras, why=why_ras)
    if any(s["level"] == "f4_ras" for s in plan["steps"]) and pay_ras and time.time() < t_end:
        ingest = next(
            (c for c in mem.by_level("pdn") if (c.knobs or {}).get("source") == "ingest_pdn"),
            None,
        )
        child = evaluate_f4_pdn(
            mem,
            {"name": "ras_residual", **GOLD_KNOBS},
            variant=variant,
            design_id=design_id,
            parent_id=(ext_hit["candidate"].id if ext_hit else (ingest.id if ingest else None)),
            spice=ext_hit["spice"] if ext_hit else None,
            insts=ext_hit["insts"] if ext_hit else None,
            extract_id=extract_id,
            solver="ras",
            sta=ext_hit.get("sta") if ext_hit else None,
        )
        if child:
            step(
                "evaluate",
                id=child.id,
                level="pdn",
                fidelity="F4",
                via="f4_solver_ras",
                extract_id=extract_id,
                droop_mv=child.qor.dynamic_ir_mv,
                em_j=child.qor.em_j_a_m2,
                gold=False,
                status=child.status,
                reason="mf-ras-residual-vs-direct",
            )

    n_krylov = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_solver_krylov"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "finish") == extract_id
    )
    pay_kry, why_kry = should_pay_f4_krylov(
        mem,
        budget_left=t_end - time.time(),
        n_krylov=n_krylov,
        variant=variant,
        extract_id=extract_id,
    )
    step("acquire", fidelity="F4_KRYLOV", pay=pay_kry, why=why_kry)
    if any(s["level"] == "f4_krylov" for s in plan["steps"]) and pay_kry and time.time() < t_end:
        ingest = next(
            (c for c in mem.by_level("pdn") if (c.knobs or {}).get("source") == "ingest_pdn"),
            None,
        )
        child = evaluate_f4_pdn(
            mem,
            {"name": "krylov_residual", **GOLD_KNOBS},
            variant=variant,
            design_id=design_id,
            parent_id=(ext_hit["candidate"].id if ext_hit else (ingest.id if ingest else None)),
            spice=ext_hit["spice"] if ext_hit else None,
            insts=ext_hit["insts"] if ext_hit else None,
            extract_id=extract_id,
            solver="krylov",
            sta=ext_hit.get("sta") if ext_hit else None,
        )
        if child:
            step(
                "evaluate",
                id=child.id,
                level="pdn",
                fidelity="F4",
                via="f4_solver_krylov",
                extract_id=extract_id,
                droop_mv=child.qor.dynamic_ir_mv,
                em_j=child.qor.em_j_a_m2,
                gold=False,
                status=child.status,
                m=(child.artifacts or {}).get("m"),
                reason="mf-krylov-mor-residual-vs-direct",
            )

    n_arr = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_host_arrivals" and c.status == "ok"
    )
    pay_arr, why_arr = should_pay_host_arrivals(
        mem, budget_left=t_end - time.time(), n_arr=n_arr
    )
    step("acquire", fidelity="F3_HOST_ARRIVALS", pay=pay_arr, why=why_arr)
    if any(s["level"] == "f4_activity" for s in plan["steps"]) and pay_arr and time.time() < t_end:
        host_arr = iscale_host(mem)
        if host_arr:
            child = evaluate_host_arrivals(host_arr, mem, design_id=design_id)
            if child:
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F3",
                    via="f4_host_arrivals",
                    parent=host_arr.id,
                    host_source=(host_arr.knobs or {}).get("source") or host_arr.level,
                    n_inst=(child.artifacts or {}).get("n_inst"),
                    status=child.status,
                    reason=why_arr,
                )

    n_host_ext = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_host_extract" and c.status == "ok"
    )
    pay_he, why_he = should_pay_f4_host_extract(
        mem, budget_left=t_end - time.time(), n_extract=n_host_ext
    )
    step("acquire", fidelity="F4_HOST_EXTRACT", pay=pay_he, why=why_he)
    if any(s["level"] == "f4_host_extract" for s in plan["steps"]) and pay_he and time.time() < t_end:
        host_ex = iscale_host(mem)
        if host_ex and (host_ex.artifacts or {}).get("mapped_v"):
            params = flowlab_params()
            util_h = float(params.get("coreUtilization") or 35.0)
            den_h = gpl_density(util_h, params.get("placeDensityAddon") or 0.2)
            arr_hit = latest_host_arrivals(mem)
            child = evaluate_f4_extract(
                host_ex,
                mem,
                design_id=design_id,
                variant=variant,
                util=util_h,
                density=den_h,
                kind="host",
                sta=arr_hit["sta"] if arr_hit else None,
            )
            if child:
                step(
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
                    reason=why_he,
                )

    n_hre = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_host_region_extract" and c.status == "ok"
    )
    pay_hre, why_hre = should_pay_f4_host_region(
        mem, budget_left=t_end - time.time(), n_extract=n_hre
    )
    step("acquire", fidelity="F4_HOST_REGION", pay=pay_hre, why=why_hre)
    if any(s["level"] == "f4_host_region" for s in plan["steps"]) and pay_hre and time.time() < t_end:
        host_rg = iscale_host(mem)
        host_ext_c = latest_host_extract_cand(mem)
        hattr = (host_ext_c.attr or {}) if host_ext_c else {}
        if host_rg and (host_rg.artifacts or {}).get("mapped_v") and (
            hattr.get("region") or hattr.get("x_dbu") is not None
        ):
            params = flowlab_params()
            util_hr = float(params.get("coreUtilization") or 35.0)
            den_hr = gpl_density(util_hr, params.get("placeDensityAddon") or 0.2)
            arr_hr = latest_host_arrivals(mem)
            child = evaluate_f4_extract(
                host_rg,
                mem,
                design_id=design_id,
                variant=variant,
                util=util_hr,
                density=den_hr,
                kind="host_region",
                region=hattr.get("region"),
                x_dbu=hattr.get("x_dbu"),
                y_dbu=hattr.get("y_dbu"),
                region_density=0.30,
                sta=arr_hr["sta"] if arr_hr else None,
            )
            if child:
                step(
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
                    reason=why_hre,
                )

    n_scale = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_iscale" and c.status == "ok"
    )
    pay_sc, why_sc = should_pay_f4_scale(
        mem, budget_left=t_end - time.time(), n_scale=n_scale, variant=variant
    )
    step("acquire", fidelity="F4_ISCALE", pay=pay_sc, why=why_sc)
    if pay_sc and time.time() < t_end:
        base_p = None
        for c in mem.by_level("logic"):
            if c.status == "ok" and c.knobs.get("name") == "liberty_default":
                _w, p = timing_of(mem, c)
                if p:
                    base_p = p
                    break
        pick = iscale_host(mem)
        if pick and base_p:
            host_hit = latest_ok_host_extract(mem)
            mesh = host_hit or ext_hit
            use_ext = bool(mesh)
            arr_hit = latest_host_arrivals(mem)
            sta = arr_hit["sta"] if arr_hit else (mesh.get("sta") if mesh else None)
            sta_via = (
                "f4_host_arrivals"
                if arr_hit
                else ("f4_host_extract" if host_hit else ("extract" if ext_hit else None))
            )
            child = evaluate_f4_scale(
                pick,
                mem,
                variant=variant,
                design_id=design_id,
                baseline_power_w=base_p,
                spice=mesh["spice"] if use_ext else None,
                insts=mesh["insts"] if use_ext else None,
                extract_id=str(mesh["extract_id"]) if use_ext else "finish",
                sta=sta,
                sta_via=sta_via,
            )
            if child:
                step(
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

    planned_ir = any(s["level"] == "ir_steer" for s in plan["steps"])
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

    planned_hir = any(s["level"] == "host_ir_steer" for s in plan["steps"])
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

    n_sw = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_iscale_win" and c.status == "ok"
    )
    pay_sw, why_sw = should_pay_f4_scale_win(
        mem, budget_left=t_end - time.time(), n_scale=n_sw, variant=variant
    )
    step("acquire", fidelity="F4_ISCALE_WIN", pay=pay_sw, why=why_sw)
    if any(s["level"] == "f4_scale_win" for s in plan["steps"]) and pay_sw and time.time() < t_end:
        base_p_w = None
        for c in mem.by_level("logic"):
            if c.status == "ok" and c.knobs.get("name") == "liberty_default":
                _w, p = timing_of(mem, c)
                if p:
                    base_p_w = p
                    break
        pick_w = iscale_parent(mem)
        win = winning_host_pdn(mem)
        eid_w = str((win.knobs or {}).get("extract_id") or win.id) if win else ""
        hit_w = extract_on_disk(mem, eid_w) if eid_w else None
        if pick_w and base_p_w and win and hit_w:
            arr_w = latest_host_arrivals(mem)
            child = evaluate_f4_scale(
                pick_w,
                mem,
                variant=variant,
                design_id=design_id,
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
            if child:
                step(
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
                    reason=why_sw,
                )

    n_irc = sum(
        1
        for c in mem.by_level("cell")
        if (c.knobs or {}).get("source") == "cell_size_ir" and c.status == "ok"
    )
    pay_irc, why_irc = should_pay_ir_cell(
        mem, budget_left=t_end - time.time(), n_cell=n_irc
    )
    step("acquire", fidelity="IR_CELL", pay=pay_irc, why=why_irc)
    if any(s["level"] == "ir_cell" for s in plan["steps"]) and pay_irc and time.time() < t_end:
        host_ic = iscale_parent(mem)
        spec_ic = ir_hotspot_cells(mem)
        if host_ic and spec_ic and spec_ic.get("cells"):
            if not (host_ic.artifacts or {}).get("mapped_v"):
                host_ic = ensure_mapped_netlist(host_ic, rtl=rtl, liberty=lib)
                mem.touch(host_ic)
            child = evaluate_cell_size(
                host_ic,
                mem,
                design_id=design_id,
                cells=list(spec_ic["cells"]),
                source="cell_size_ir",
            )
            if child:
                step(
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
                    reason=why_irc,
                )

    synth_f0 = propose_synthesis_f0(mem, design_id, current_abc_area=flowlab_params().get("abcArea"))
    for c in synth_f0:
        step("propose", level="synthesis", knobs=c.knobs, fidelity="F0")

    front = {
        lv: pareto_front((c.id, c.qor) for c in mem.by_level(lv) if c.status == "ok")
        for lv in LEVELS
    }
    pred = predict_f1_area(mem.by_level("logic"))
    f4s = predict_f4_from_f1(mem.all())
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
            if (c.knobs or {}).get("source")
            in (
                "f4_solver_a",
                "f4_iscale",
                "f4_iscale_win",
                "f4_candidate_extract",
                "f4_host_extract",
                "f4_host_region_extract",
                "f4_region_extract",
                "f4_solver_amg",
                "f4_solver_ras",
                "f4_solver_krylov",
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
        "plan": plan,
        "attribution": attr,
        "focus": focus,
        "pareto": {
            **front,
            "note": "frontiers are per level; do not rank ABC area against IR droop",
        },
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
        cand.attr["delta"] = {
            "vs": base.id,
            "area_um2": float(cand.qor.area_um2) - float(base.qor.area_um2),
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
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_solver_ras" and c.qor.dynamic_ir_mv is not None:
            ras = f" · RAS residual {c.qor.dynamic_ir_mv:.3f} mV (not gold)"
            break
    kry = ""
    for c in mem.by_level("pdn"):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_solver_krylov" and c.qor.dynamic_ir_mv is not None:
            kry = f" · Krylov/MOR residual {c.qor.dynamic_ir_mv:.3f} mV m={(c.artifacts or {}).get('m')} (not gold)"
            break
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
            mods = ",".join((c.attr or {}).get("modules") or []) or ",".join(
                {str(x).split("/")[0] for x in (c.knobs or {}).get("cells") or [] if "/" in str(x)}
            )
            ircell = (
                f" · IR-cell size-up n={nch} {mods} WNS={w:+.3f} ns"
                if w is not None
                else f" · IR-cell size-up n={nch} {mods}"
            )
            break
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
        f"best mapped area {best}{ctrlc}{synth}{cell}{ircell}{netb}{netp}{psteer}{wns}{f5}{f5cts}{f5loc}{f5port}{steers}{irst}{hirst}{arrs}{isc} · IR cone {mods}{ir}{ras}{kry}"
    )

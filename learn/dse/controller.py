"""Budget-aware DSE controller. One level per proposal — never a flat box.

Loop: inspect → propose (level, knobs) → pick fidelity → evaluate → attribute
→ update memory / Pareto → next.

Optimizers (each on its own level):
  architecture — e-graph extract of the IR-attributed dpath cone (ROVER/ASPEN shape)
  logic        — BOiLS SSK-GP + EHVI(area, WNS) / EI, DRiLLS sequential append
  synthesis    — ORFS ABC_AREA catalog (F0)
  physical     — F2-fast + budgeted GPL + AutoDMP catalog GPL + ingest + F0 proxy
  routing      — budgeted OpenROAD GRT (not detailed route / F5)
  pdn          — F4 ingest + budgeted Solver A restamp (knobs / I-scale; not gold)

Acquisition ≈ expected improvement + information − compute − extrapolation risk.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from .abc_space import CATALOG
from .acquire import (
    should_pay_f2_fast,
    should_pay_f2_gpl,
    should_pay_f2_grt,
    should_pay_f3_sta,
    should_pay_f4_pdn,
    should_pay_f4_scale,
    should_pay_physical_catalog,
)
from .arch_space import emit_gcd_variant
from .attribute import attribute_from_path, local_scope
from .boils import propose_logic_boils, should_pay_f1
from .fidelity import (
    COST_HINT,
    evaluate_f1_abc,
    evaluate_f2_fast,
    evaluate_f2_gpl,
    evaluate_f2_grt,
    evaluate_f3_sta,
    evaluate_f4_pdn,
    evaluate_f4_scale,
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
from .pdn_space import next_pdn_spec
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
    residual,
)

LEVELS = ("architecture", "logic", "synthesis", "physical", "routing", "pdn")


def propose_logic(mem: DesignMemory, focus: str = "chip") -> dict | None:
    """Public hook used by tests: a logic proposal never carries physical knobs."""
    return propose_logic_boils(mem, focus=focus)


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
        while n_arch < arch_max and n_f1 < f1_max and time.time() < t_end:
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

    while n_f1 < f1_max and time.time() < t_end:
        knobs = propose_logic_boils(mem, focus=str(plan.get("focus") or "chip"))
        if knobs is None:
            extra = next(
                (
                    p
                    for p in propose_from_attr(mem, focus=str(plan.get("focus") or "chip"), attr=attr)
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
    n_pdn_f4 = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_solver_a" and c.status == "ok"
    )
    pay_pdn, why_pdn = should_pay_f4_pdn(
        mem, budget_left=t_end - time.time(), n_pdn=n_pdn_f4, variant=variant
    )
    step("acquire", fidelity="F4_PDN", pay=pay_pdn, why=why_pdn)
    spec_pdn = next_pdn_spec(mem) if pay_pdn else None
    if spec_pdn and time.time() < t_end:
        ingest = next(
            (c for c in mem.by_level("pdn") if (c.knobs or {}).get("source") == "ingest_pdn"),
            None,
        )
        child = evaluate_f4_pdn(
            mem, spec_pdn, variant=variant, design_id=design_id, parent_id=ingest.id if ingest else None
        )
        if child:
            step(
                "evaluate",
                id=child.id,
                level="pdn",
                fidelity="F4",
                via="f4_solver_a",
                catalog=spec_pdn.get("name"),
                droop_mv=child.qor.dynamic_ir_mv,
                gold=False,
                status=child.status,
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
        pick = None
        for cand in (f1_wns_winner(mem), f1_area_winner(mem), *f1_ok(mem)):
            if cand is None or base_p is None:
                continue
            _w, p = timing_of(mem, cand)
            if p is None or abs(float(p) / float(base_p) - 1.0) < 0.03:
                continue
            pick = cand
            break
        if pick and base_p:
            child = evaluate_f4_scale(
                pick, mem, variant=variant, design_id=design_id, baseline_power_w=base_p
            )
            if child:
                step(
                    "evaluate",
                    id=child.id,
                    level="pdn",
                    fidelity="F4",
                    via="f4_iscale",
                    parent=pick.id,
                    i_scale=(child.knobs or {}).get("i_scale"),
                    droop_mv=child.qor.dynamic_ir_mv,
                    gold=False,
                    status=child.status,
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
            "F1 Yosys+ABC+equiv (script file, write_verilog -noexpr) on logic and dpath extracts",
            "F2 ingest + F2-fast netgraph + budgeted GPL + catalog GPL + budgeted GRT",
            "F3 OpenSTA interleaved after each F1 (ideal) + ingest signoff STA",
            "F4 ingest gold + Solver A restamp (PDN knobs / I(t)×power) — gold unrestamped",
            "IR combo on dpath → cone extracts; F3 WNS reorders remaining, no chip restart",
            "hierarchy chip→block→region→cone; attributed cells/region from hotspot",
            "Pareto per level — EHVI acquires, it does not replace the front",
            "BOiLS EHVI(area,WNS) · DRiLLS UCB+IR · GNN HPWL · AutoDMP GPL · PDN F4",
        ],
        "not": [
            "flattened black-box of all knobs",
            "neural voltage map as sign-off",
            "automatic P&R launch from the controller (F5 GAP)",
            "LLM as the optimizer (proposer-only; DSE_LLM_URL optional)",
        ],
        "layers": adapter_status(),
        "budget_s": budget_s,
        "spent_s": sum(c.cost_s for c in mem.all()),
        "n_candidates": len(mem),
        "n_f1": sum(1 for c in mem.all() if c.fidelity == "F1"),
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
        "n_f3": sum(1 for c in mem.all() if c.fidelity == "F3"),
        "n_f2_grt": sum(
            1
            for c in mem.by_level("routing")
            if c.knobs.get("source") == "f2_openroad_grt"
        ),
        "n_f4": sum(1 for c in mem.by_level("pdn") if c.fidelity == "F4"),
        "n_f4_solve": sum(
            1
            for c in mem.by_level("pdn")
            if (c.knobs or {}).get("source") in ("f4_solver_a", "f4_iscale")
        ),
        "memory": str(mem_path),
        "surrogate_f0": pred,
        "surrogate_f1_to_f2": predict_f2_from_f1(mem.all()),
        "surrogate_f1_to_f2_gnn": predict_f2_gnn(mem.all()),
        "surrogate_f1_to_gpl": predict_gpl_from_f1(mem.all()),
        "surrogate_f1_to_wns": predict_wns_from_f1(mem.all()),
        "surrogate_f1_to_power": predict_power_from_f1(mem.all()),
        "surrogate_f1_to_f4": f4s,
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
        if c.qor.dynamic_ir_mv is not None:
            ir = f" · F4 droop {c.qor.dynamic_ir_mv:.3f} mV (ingest, not gold replace)"
            break
    wns = ""
    timed = [
        (c.knobs.get("parent_name") or c.knobs.get("name"), c.qor.wns_cost)
        for c in mem.all()
        if c.status == "ok" and c.qor.wns_cost is not None and c.fidelity == "F3"
    ]
    if timed:
        timed.sort(key=lambda t: t[1])
        wns = f" · best ideal WNS {-timed[0][1]:+.3f} ns ({timed[0][0]})"
    mods = ",".join(attr.get("modules") or []) or "unjoined"
    return (
        f"DSE {len(mem)} candidates · F1 {n_f1} (arch {n_arch}) · logic Pareto {len(front_logic)} · "
        f"best mapped area {best}{wns} · IR cone {mods}{ir}"
    )

"""Budget-aware DSE controller. One level per proposal — never a flat box.

Loop: inspect → propose (level, knobs) → pick fidelity → evaluate → attribute
→ update memory / Pareto → next.

Optimizers (each on its own level):
  architecture — e-graph extract of the IR-attributed dpath cone (ROVER/ASPEN shape)
  logic        — BOiLS SSK-GP + EI, DRiLLS sequential append
  synthesis    — ORFS ABC_AREA catalog (F0)
  physical     — F2-fast netgraph + budgeted OpenROAD GPL + ingest + AutoDMP F0
  pdn          — F4 ingest only

Acquisition ≈ expected improvement + information − compute − extrapolation risk.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from .abc_space import CATALOG
from .acquire import should_pay_f2_fast, should_pay_f2_gpl
from .arch_space import emit_gcd_variant
from .attribute import attribute_from_path, local_scope
from .boils import propose_logic_boils, should_pay_f1
from .fidelity import (
    COST_HINT,
    evaluate_f1_abc,
    evaluate_f2_fast,
    evaluate_f2_gpl,
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
from .physical_space import propose_physical_f0, propose_synthesis_f0
from .planner import plan_search
from .proposer import propose as propose_from_attr
from .surrogate import (
    predict_f1_area,
    predict_f2_from_f1,
    predict_f2_gnn,
    predict_f4_from_f1,
    predict_gpl_from_f1,
    residual,
)

LEVELS = ("architecture", "logic", "synthesis", "physical", "pdn")


def propose_logic(mem: DesignMemory, focus: str = "chip") -> dict | None:
    """Public hook used by tests: a logic proposal never carries physical knobs."""
    return propose_logic_boils(mem, focus=focus)


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
    log: list[dict] = []

    def step(kind: str, **kw):
        log.append({"t": time.time(), "kind": kind, **kw})

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

    lib = liberty_path()
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

    # Hierarchical architecture: planner orders extracts from IR attribution.
    arch_step = next((s for s in plan["steps"] if s["level"] == "architecture"), None)
    if arch_step and time.time() < t_end:
        from .arch_space import plan_dpath_extracts

        _eg, _roots, _ex, stats = plan_dpath_extracts()
        extracts = list(arch_step.get("extracts") or _ex)
        step("egraph", **{k: stats[k] for k in ("n_enodes", "n_eclasses", "rules_fired", "extracts")})
        step("arch_reason", reason=arch_step.get("reason"))
        seen_arch = mem.seen_knobs("architecture")
        for name in extracts:
            if n_arch >= arch_max or n_f1 >= f1_max or time.time() >= t_end:
                break
            knobs = {
                "name": name,
                "module": "dpath",
                "extract": name,
                "scope": "logic_cone",
                "abc_script": "file",
            }
            if knobs_fp("architecture", knobs) in seen_arch:
                continue
            if time.time() + COST_HINT["F1"] > t_end and n_f1:
                step("stop", reason="budget would not cover architecture F1")
                break
            with tempfile.TemporaryDirectory(prefix="dse-arch-") as tmp:
                dest = Path(tmp) / f"gcd_{name}.v"
                try:
                    meta = emit_gcd_variant(rtl, name, dest)
                except ValueError as exc:
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
        pay, why = should_pay_f1(pred, best)
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

    # F2-fast on the best F1 netlists (logic + architecture winners).
    n_f2 = 0
    pay_fast, why_fast = should_pay_f2_fast(mem, n_f2=n_f2)
    if any(s["level"] == "f2_fast" for s in plan["steps"]) and pay_fast and time.time() < t_end:
        winners = []
        for lv in ("logic", "architecture"):
            ranked = [
                c
                for c in mem.by_level(lv)
                if c.status == "ok" and c.qor.area_um2 is not None
            ]
            ranked.sort(key=lambda c: float(c.qor.area_um2))
            winners.extend(ranked[:2])
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
        ranked = [
            c
            for c in mem.all()
            if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None
        ]
        ranked.sort(key=lambda c: float(c.qor.area_um2))
        pick = None
        for cand in ranked:
            w = ensure_mapped_netlist(cand, rtl=rtl, liberty=lib)
            mapped = (w.artifacts or {}).get("mapped_v")
            if mapped and is_gate_cell_netlist(Path(mapped)):
                pick = w
                break
        if pick:
            w = pick
            mem.touch(w)
            child = evaluate_f2_gpl(w, mem, design_id=design_id)
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

    phys_f0 = propose_physical_f0(mem, design_id)
    for c in phys_f0:
        step("propose", level="physical", knobs=c.knobs, fidelity="F0")
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
            "layered search: architecture e-graph ≠ logic ABC ≠ synthesis ABC_AREA ≠ physical ≠ PDN",
            "F0 SSK-GP area + RUDY-class congestion; not IR",
            "F1 Yosys+ABC+equiv (script file, write_verilog -noexpr) on logic and dpath extracts",
            "F2 ingest of OpenROAD place/GRT + F2-fast netgraph + budgeted GPL skip_io",
            "F3/F4 ingest of OpenSTA + Dynamic IR (Solver A gold unrestamped)",
            "IR combo on dpath → planner orders cone extracts (lt/sub/eqz), no chip restart",
            "hierarchy chip→block→region→cone; attributed cells/region from hotspot",
            "Pareto per level — no premature scalar",
            "BOiLS SSK-GP + EI · DRiLLS UCB · GNN HPWL residual · AutoDMP F0 · GPL F2",
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
        "memory": str(mem_path),
        "surrogate_f0": pred,
        "surrogate_f1_to_f2": predict_f2_from_f1(mem.all()),
        "surrogate_f1_to_f2_gnn": predict_f2_gnn(mem.all()),
        "surrogate_f1_to_gpl": predict_gpl_from_f1(mem.all()),
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
    mods = ",".join(attr.get("modules") or []) or "unjoined"
    return (
        f"DSE {len(mem)} candidates · F1 {n_f1} (arch {n_arch}) · logic Pareto {len(front_logic)} · "
        f"best mapped area {best} · IR cone {mods}{ir}"
    )

"""Campaign contracts: shared JSONL, HV stop, zero-new, wall, default shots.

Fake inner runner only — no OpenROAD, no AES, no F4, no ``run_controller``.
"""
from __future__ import annotations

import inspect
import tempfile
from pathlib import Path

from dse.acquire import should_pay_cell_size, should_pay_f5_cts
from dse.campaign import DEFAULT_SHOTS, lifetime_shots, run_campaign, suggest_ref
from dse.memory import Candidate, DesignMemory
from dse.metrics import QoR
from dse.planner import parent_queue, pred_costs


def _cand(cid: str, *, area: float, wns: float, pred_mean=None, **kw) -> Candidate:
    return Candidate(
        id=cid,
        design_id="gcd",
        parent_id=kw.get("parent_id"),
        level=kw.get("level") or "logic",
        knobs=kw.get("knobs") or {"name": cid},
        knobs_fp=cid,
        rtl_fp="x",
        netlist_fp="y",
        fidelity=kw.get("fidelity") or "F1",
        qor=QoR(area_um2=area, wns_cost=wns, fidelity=kw.get("fidelity") or "F1"),
        cost_s=0.0,
        pred={"mean": pred_mean} if pred_mean is not None else {},
        status=kw.get("status") or "ok",
    )


def _scripted(batches: list[list[tuple[float, float]]], seen: list | None = None):
    state = {"i": 0}

    def runner(**kw):
        if seen is not None:
            seen.append(kw)
        path = Path(kw["memory_path"])
        mem = DesignMemory(path)
        i = state["i"]
        state["i"] += 1
        added = 0
        if i < len(batches):
            for j, (area, wns) in enumerate(batches[i]):
                mem.add(_cand(f"i{i}p{j}", area=area, wns=wns))
                added += 1
        return {"ok": True, "n_new": added}

    return runner, state


def check_campaign(check) -> None:
    check(lifetime_shots(0) == DEFAULT_SHOTS, "inner 0 lifetime shots equal today's defaults")
    check(DEFAULT_SHOTS["gpl"] == 1, "default GPL max_shots is 1")
    check(DEFAULT_SHOTS["f5"] == 1, "default F5 max_shots is 1")
    check(DEFAULT_SHOTS["f5_cts"] == 1, "default F5-CTS max_shots is 1")
    check(DEFAULT_SHOTS["cell"] == 1, "default cell max_shots is 1")
    check(DEFAULT_SHOTS["net"] == 1, "default net max_shots is 1")
    check(DEFAULT_SHOTS["f2_fast"] == 4, "default F2-fast max_shots is 4")
    check(DEFAULT_SHOTS["f3"] == 8, "default F3 max_shots is 8")
    check(lifetime_shots(1)["gpl"] == 2, "inner 1 raises GPL lifetime cap to 2")
    check(lifetime_shots(1)["f3"] == 9, "inner 1 raises F3 lifetime cap by one")

    a = _cand("a", area=100, wns=1.0, pred_mean=3.0)
    b = _cand("b", area=90, wns=1.1, pred_mean=1.0)
    c = _cand("c", area=80, wns=1.2, pred_mean=2.0)
    q_skip = parent_queue([a, b, c], have_child_ids={"b"})
    check([x.id for x in q_skip] == ["a", "c"], "parent_queue skips parents that already have a child")
    q_pred = parent_queue([a, b, c], pred_by_id={"a": 3.0, "b": 1.0, "c": 2.0})
    check([x.id for x in q_pred] == ["b", "c", "a"], "parent_queue reorders by pred when provided")
    q_keep = parent_queue([a, b, c], pred_by_id={})
    check([x.id for x in q_keep] == ["a", "b", "c"], "empty pred preserves first-run order")

    tmp = Path(tempfile.mkdtemp(prefix="dse-camp-"))
    mem = DesignMemory(tmp / "pred.jsonl")
    mem.add(a)
    mem.add(_cand("z", area=1, wns=1))  # no pred mean
    costs = pred_costs(mem)
    check(costs.get("a") == 3.0 and "z" not in costs, "pred_costs reads Candidate.pred mean only")

    wall = run_campaign(
        inner_runner=lambda **kw: {"ok": True},
        memory_path=tmp / "wall.jsonl",
        wall_s=0,
        max_inner=4,
    )
    check(wall["n_inner"] == 0 and wall["stop"] == "wall", "wall_s=0 runs zero inners")

    zero_runner, _ = _scripted([[]])
    zero = run_campaign(
        inner_runner=zero_runner,
        memory_path=tmp / "zero.jsonl",
        wall_s=30,
        max_inner=4,
        hv_eps=1e-3,
    )
    check(zero["stop"] == "zero_new" and zero["n_inner"] == 1, "stop on zero new ok candidates")

    seen: list = []
    shared_path = tmp / "shared.jsonl"
    shared_runner, _ = _scripted([[(120.0, 1.2)], [(100.0, 1.0)]], seen=seen)
    shared = run_campaign(
        inner_runner=shared_runner,
        memory_path=shared_path,
        wall_s=30,
        max_inner=2,
        hv_eps=1e-9,
        f1_max_per_run=6,
    )
    mem_s = DesignMemory(shared_path)
    ids = {c.id for c in mem_s.all()}
    check(len(mem_s) == 2 and ids == {"i0p0", "i1p0"}, "campaign reuses one JSONL; ids accumulate")
    check(all(kw["memory_path"] == shared_path for kw in seen), "every inner receives the same memory_path")
    check(seen[0]["f1_max"] == 6 and seen[1]["f1_max"] == 12, "f1_max grows as per-run × (inner+1)")
    check(seen[0]["max_shots"]["gpl"] == 1 and seen[1]["max_shots"]["gpl"] == 2, "GPL cap grows per inner")
    check(seen[0]["fresh"] is False and seen[1]["fresh"] is False, "campaign never wipes between inners")

    hv_runner, _ = _scripted(
        [
            [(100.0, 1.0)],
            [(80.0, 0.8)],
            [(90.0, 0.9)],
        ]
    )
    hv = run_campaign(
        inner_runner=hv_runner,
        memory_path=tmp / "hv.jsonl",
        wall_s=30,
        max_inner=8,
        hv_eps=1e-3,
    )
    check(hv["stop"] == "hv_eps", f"HV stall stops the campaign, got {hv['stop']}")
    check(hv["n_inner"] == 3, f"HV grows then stalls after the dominated inner, got {hv['n_inner']}")
    series = hv["hv"]
    check(len(series) == 3 and series[1] > series[0], "HV grows when a dominating logic point is added")
    check(abs(series[2] - series[1]) < 1e-9, "dominated logic point does not grow HV")
    check(hv["ref"] is not None and hv["ref"][0] > 100.0, "HV reference is frozen from the first front")
    frozen = tuple(hv["ref"])
    first_pts = [(100.0, 1.0)]
    check(suggest_ref(first_pts) == frozen, "suggest_ref matches the frozen campaign nadir")

    mem_pay = DesignMemory(tmp / "pay.jsonl")
    mem_pay.add(
        Candidate(
            id="cell0",
            design_id="gcd",
            parent_id="p0",
            level="cell",
            knobs={"source": "cell_size_up"},
            knobs_fp="cell0",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=10, fidelity="F3"),
            cost_s=1.0,
            status="ok",
        )
    )
    pay1, why1 = should_pay_cell_size(mem_pay, budget_left=80, n_cell=0, cell_max=1)
    check(not pay1 and why1 == "already have a cell-local size child", f"max=1 keeps already-have why ({why1})")
    pay2, why2 = should_pay_cell_size(mem_pay, budget_left=80, n_cell=0, cell_max=2)
    check(why2 != "already have a cell-local size child", f"raised cell_max skips already-have ({why2})")

    mem_pay.add(
        Candidate(
            id="f5lite",
            design_id="gcd",
            parent_id="t0",
            level="routing",
            knobs={"source": "f5_openroad_drt_rcx"},
            knobs_fp="f5lite",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F5",
            qor=QoR(wns_cost=0.6, fidelity="F5"),
            cost_s=1.0,
            status="ok",
        )
    )
    mem_pay.add(
        Candidate(
            id="cts0",
            design_id="gcd",
            parent_id="t0",
            level="routing",
            knobs={"source": "f5_openroad_cts_rcx"},
            knobs_fp="cts0",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F5",
            qor=QoR(wns_cost=0.5, fidelity="F5"),
            cost_s=1.0,
            status="ok",
        )
    )
    pay_c, why_c = should_pay_f5_cts(mem_pay, budget_left=80, n_f5_cts=0, f5_cts_max=1)
    check(not pay_c and why_c == "already have a CTS SPEF child", f"CTS max=1 keeps already-have ({why_c})")
    pay_c2, why_c2 = should_pay_f5_cts(mem_pay, budget_left=80, n_f5_cts=0, f5_cts_max=2)
    check(why_c2 != "already have a CTS SPEF child", f"raised f5_cts_max skips already-have ({why_c2})")

    sig = inspect.signature(run_campaign)
    check("inner_runner" in sig.parameters, "run_campaign injects a fake inner runner")
    cli = (Path(__file__).resolve().parents[2] / "learn/scripts/run_dse.py").read_text()
    check("--campaign" in cli and "run_campaign" in cli, "CLI --campaign is opt-in")
    check("default: one controller pass" in cli or "default remains" in cli or "--campaign" in cli, "single pass stays the default")

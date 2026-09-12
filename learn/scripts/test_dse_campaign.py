"""Current-invocation campaign contracts; no external run data is read."""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path

from dse.acquire import should_pay_cell_size, should_pay_f5_cts
from dse.campaign import (
    DEFAULT_SHOTS,
    infer_start_inner,
    lifetime_shots,
    occupancy,
    run_campaign,
    suggest_ref,
)
from dse.memory import Candidate, DesignMemory
from dse.metrics import QoR
from dse.planner import parent_queue, pred_costs


def _cand(cid: str, *, area: float, wns: float, pred_mean=None, **kw) -> Candidate:
    return Candidate(
        id=cid,
        design_id="fixture",
        parent_id=kw.get("parent_id"),
        level=kw.get("level") or "logic",
        knobs=kw.get("knobs") or {"name": cid},
        knobs_fp=cid,
        rtl_fp="fixture-rtl",
        netlist_fp="fixture-netlist",
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
        mem = DesignMemory(Path(kw["memory_path"]))
        i = state["i"]
        state["i"] += 1
        added = 0
        for j, (area, wns) in enumerate(batches[i] if i < len(batches) else []):
            mem.add(_cand(f"i{i}p{j}", area=area, wns=wns))
            added += 1
        return {"ok": True, "n_new": added}

    return runner


def check_campaign(check) -> None:
    check(lifetime_shots(0) == DEFAULT_SHOTS, "inner zero uses declared live caps")
    check(infer_start_inner(DesignMemory(Path(tempfile.mkdtemp()) / "empty.jsonl")) == 0, "empty run starts at zero")

    a = _cand("a", area=100, wns=1.0, pred_mean=3.0)
    b = _cand("b", area=90, wns=1.1, pred_mean=1.0)
    c = _cand("c", area=80, wns=1.2, pred_mean=2.0)
    check([x.id for x in parent_queue([a, b, c], have_child_ids={"b"})] == ["a", "c"], "parent queue skips measured parents")
    check([x.id for x in parent_queue([a, b, c], pred_by_id={"a": 3.0, "b": 1.0, "c": 2.0})] == ["b", "c", "a"], "parent queue uses current predictions")
    mem = DesignMemory(Path(tempfile.mkdtemp()) / "pred.jsonl")
    mem.add(a)
    check(pred_costs(mem) == {"a": 3.0}, "prediction costs come from current candidates")

    tmp = Path(tempfile.mkdtemp(prefix="dse-live-campaign-"))
    stale = tmp / "stale.jsonl"
    DesignMemory(stale).add(_cand("stale", area=1, wns=1))
    zero = run_campaign(
        inner_runner=_scripted([[]]),
        memory_path=stale,
        wall_s=30,
        max_inner=2,
    )
    check(zero["stop"] == "zero_new" and zero["n_inner"] == 1, "zero-new current run stops cleanly")
    check(not DesignMemory(stale).get("stale"), "invocation boundary removes stale memory")
    check(zero["comparison_scope"] == "same-live-invocation", "campaign declares its scope")

    seen: list = []
    shared = tmp / "shared.jsonl"
    result = run_campaign(
        inner_runner=_scripted([[(120.0, 1.2)], [(100.0, 1.0)]], seen=seen),
        memory_path=shared,
        wall_s=30,
        max_inner=2,
        hv_eps=1e-9,
        f1_max_per_run=6,
    )
    check(len(DesignMemory(shared)) == 2, "one current invocation accumulates inner results")
    check(all(kw["memory_path"] == shared for kw in seen), "inners share the explicit current memory")
    check(seen[0]["f1_max"] == 6 and seen[1]["f1_max"] == 12, "inner caps are scoped and increase within the run")
    check(tuple(result["ref"]) == suggest_ref([(120.0, 1.2)]), "HV reference derives from current points")

    pay_mem = DesignMemory(tmp / "pay.jsonl")
    pay_mem.add(_cand("cell0", area=10, wns=1, level="cell", fidelity="F3", knobs={"source": "cell_size_up"}))
    pay, why = should_pay_cell_size(pay_mem, budget_left=80, n_cell=0, cell_max=1)
    check(not pay and "cell" in why, "cell capacity honors current memory")
    pay_mem.add(_cand("cts0", area=10, wns=1, level="routing", fidelity="F5", knobs={"source": "f5_openroad_cts_rcx"}))
    pay, why = should_pay_f5_cts(pay_mem, budget_left=80, n_f5_cts=0, f5_cts_max=1)
    check(not pay and ("CTS" in why or "OpenRCX" in why), "CTS capacity honors current memory")

    sig = inspect.signature(run_campaign)
    check("memory_path" in sig.parameters and "inner_runner" in sig.parameters, "campaign accepts explicit run inputs")
    cli = (Path(__file__).resolve().parents[2] / "learn/scripts/run_dse.py").read_text()
    check("--campaign" in cli and "run_campaign" in cli, "CLI campaign mode is explicit")

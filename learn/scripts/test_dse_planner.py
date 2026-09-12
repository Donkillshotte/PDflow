"""Planner contracts for live, level-aware acquisition."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from dse.memory import Candidate, DesignMemory
from dse.metrics import QoR
from dse.planner import have_child_parents, next_candidate_ids, parent_queue, plan_search, prefer_gated


def check_planner(check, *, root: Path, mem: DesignMemory, mem2: DesignMemory) -> None:
    a = Candidate(
        id="a", design_id="gcd", parent_id=None, level="logic", knobs={"name": "a"}, knobs_fp="a",
        rtl_fp="rtl", netlist_fp=None, fidelity="F1", qor=QoR(area_um2=10.0, wns_cost=0.5, fidelity="F1"), cost_s=0.0,
    )
    b = Candidate(
        id="b", design_id="gcd", parent_id=None, level="logic", knobs={"name": "b"}, knobs_fp="b",
        rtl_fp="rtl", netlist_fp=None, fidelity="F1", qor=QoR(area_um2=12.0, wns_cost=0.7, fidelity="F1"), cost_s=0.0,
    )
    with TemporaryDirectory(prefix="pdflow-planner-") as tmp:
        local = DesignMemory(Path(tmp) / "planner-current.jsonl")
        local.add(a)
        local.add(b)
        ids = next_candidate_ids(local, "logic")
        check(ids == ["a"], f"planner keeps the current Pareto point, got {ids}")
        check(parent_queue([a, b], have_child_ids={"a"}) == [b], "planner excludes already-evaluated parents")
        check(have_child_parents(local, source="current_run") == set(), "planner has no implicit child history")
        kept = prefer_gated(local, "logic", [a, b])
        check(kept and kept[0].id == "a", "planner preserves the gated current front")
        plan = plan_search({"modules": ["dpath"], "combo_frac": 0.8, "scope": "logic_cone"}, local, f2_cong=None)
        check(any(step.get("level") == "architecture" for step in plan["steps"]), "planner routes a live cone signal to architecture")


if __name__ == "__main__":
    print("test_dse_planner is exercised by test_dse.py")

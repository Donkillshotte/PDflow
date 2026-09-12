#!/usr/bin/env python3
"""Current-run DSE contracts: schema, feasibility, provenance and routing."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(ROOT / "learn"))

from dse.contracts import stamp_evidence  # noqa: E402
from dse.f6_finish import parse_6_report, qor_from_finish  # noqa: E402
from dse.feasibility import constraint_dominates, feasibility_of, ir_comparable  # noqa: E402
from dse.fingerprint import knobs_fp  # noqa: E402
from dse.flow_role import validate_variant  # noqa: E402
from dse.memory import Candidate, DesignMemory  # noqa: E402
from dse.metrics import QoR  # noqa: E402
from dse.pdn_provenance import same_extract_delta  # noqa: E402
from dse.scheduler import next_action  # noqa: E402


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def candidate(*, ident: str, fidelity: str = "F3", qor: QoR | None = None, **extra) -> Candidate:
    return Candidate(
        id=ident,
        design_id="fixture",
        parent_id=None,
        level="logic",
        knobs={"source": "test"},
        knobs_fp=knobs_fp("logic", {"source": "test"}),
        rtl_fp="fixture",
        netlist_fp=None,
        fidelity=fidelity,
        qor=qor or QoR(area_um2=100.0, wns_cost=0.1, fidelity=fidelity),
        cost_s=0.0,
        status="ok",
        **extra,
    )


def check_next_level(check_fn, root: Path) -> None:
    memory_path = root / "learn/sim/dse/memory_flowlab.jsonl"
    if memory_path.is_file():
        memory = DesignMemory(memory_path)
        check_fn(len(memory) > 0, "current DSE memory loads")
        row = next(iter(memory.all()))
        check_fn(row.schema_version >= 1, "schema version is present")
        check_fn(isinstance(row.finish_ready, bool), "finish readiness is typed")
    else:
        check_fn(True, "current DSE memory is optional")

    open_finish = candidate(
        ident="open-finish",
        fidelity="F6",
        qor=QoR(area_um2=140.0, wns_cost=0.02, fidelity="F6"),
        artifacts={"finish_wns_ns": -0.02, "finish_tns_ns": -0.1, "flow_errors": 0},
        semantic_contract={"status": "pass"},
        finish_ready=True,
    )
    closed_finish = candidate(
        ident="closed-finish",
        fidelity="F6",
        qor=QoR(area_um2=150.0, wns_cost=0.0, tns_cost=0.0, fidelity="F6"),
        artifacts={"finish_wns_ns": 0.001, "finish_tns_ns": 0.0, "flow_errors": 0},
        semantic_contract={"status": "pass"},
        finish_ready=True,
    )
    stamp_evidence(open_finish, "wns", -0.02, "finish")
    stamp_evidence(closed_finish, "wns", 0.001, "finish")
    stamp_evidence(closed_finish, "tns", 0.0, "finish")
    check_fn(not feasibility_of(open_finish).feasible, "open finish remains infeasible")
    check_fn(feasibility_of(closed_finish).feasible, "closed finish is feasible")
    check_fn(constraint_dominates(closed_finish, open_finish), "closed finish dominates open finish")

    host = candidate(
        ident="host",
        fidelity="F4",
        qor=QoR(dynamic_ir_mv=8.0, fidelity="F4"),
        artifacts={"extract_id": "run_mesh"},
        evidence={"dynamic_ir_mv": {"value": 8.0, "source": "directlu", "artifact": "run_mesh"}},
    )
    same = candidate(
        ident="same-mesh",
        fidelity="F4",
        qor=QoR(dynamic_ir_mv=6.0, fidelity="F4"),
        artifacts={"extract_id": "run_mesh"},
        evidence={"dynamic_ir_mv": {"value": 6.0, "source": "directlu", "artifact": "run_mesh"}},
    )
    other = candidate(
        ident="other-mesh",
        fidelity="F4",
        qor=QoR(dynamic_ir_mv=2.0, fidelity="F4"),
        artifacts={"extract_id": "other_mesh"},
        evidence={"dynamic_ir_mv": {"value": 2.0, "source": "directlu", "artifact": "other_mesh"}},
    )
    delta = same_extract_delta(host, same)
    check_fn(delta.ok and delta.delta_mv < 0, "same-run extract delta is available")
    check_fn(not same_extract_delta(host, other).ok, "cross-extract delta is refused")
    check_fn(not ir_comparable(host, other), "cross-extract IR is not comparable")

    check_fn(validate_variant("fixture") == "fixture", "live variant validation")
    try:
        validate_variant("../outside")
    except ValueError:
        check_fn(True, "path traversal variant is rejected")
    else:
        check_fn(False, "path traversal variant was accepted")

    memory = DesignMemory(Path(tempfile.mkdtemp(prefix="pdflow-dse-") ) / "memory.jsonl")
    memory.add(candidate(ident="sched", fidelity="F2", qor=QoR(area_um2=90.0, wns_cost=0.2, fidelity="F2")))
    action = next_action(memory, budget_s=30, finish_shots_left=1)
    check_fn(action.kind in {"reject", "equiv", "finish"}, "scheduler returns a typed action")

    finish_report = root / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab/6_report.json"
    if finish_report.is_file():
        parsed = parse_6_report(finish_report)
        check_fn(parsed.get("wns_setup_ns") is not None, "current finish report has WNS")
        check_fn(qor_from_finish(parsed).fidelity == "F6", "current finish report maps to F6")
    else:
        check_fn(True, "current finish report is optional")

    experiments = (root / "learn/dse/experiments.py").read_text()
    check_fn("validate_variant" in experiments and "refuse_locked_variant" not in experiments, "experiment registry accepts live variants")
    launch = (root / "learn/scripts/record_dse_launch.py").read_text()
    check_fn("comparison_scope" in launch, "DSE snapshot declares its current scope")
    run_script = (root / "scripts/run_design_finish.sh").read_text()
    check_fn("LOCKED=" not in run_script and "is locked" not in run_script, "finish wrapper has no stale variant gate")
    print("ALL test_dse_next PASSED")


if __name__ == "__main__":
    check_next_level(check, ROOT)

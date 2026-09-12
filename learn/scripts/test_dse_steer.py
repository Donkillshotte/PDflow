"""Steering contracts: measurements stay attached to their live lineage."""
from dse.memory import Candidate, DesignMemory
from dse.metrics import QoR
from dse.solve_result import normalize_solve, solver_role


def check_steer(check) -> None:
    check(solver_role("direct", "direct") == "reference", "DirectLU is the reference only inside its live solve group")
    check(solver_role("amg", "amg") == "accelerator", "AMG remains an accelerator in the current solve group")
    solve = normalize_solve(
        {"status": "ok", "solver": "amg", "droop_mv": 3.2, "reference_droop_mv": 3.0,
         "abs_err_vs_reference_mv": 0.2},
        reference_droop_mv=3.0,
    )
    check(solve.status == "ok", "solver result keeps current status")
    check(solve.abs_err_vs_reference_mv == 0.2, "solver residual uses an explicit same-run reference")
    mem = DesignMemory("/tmp/dse-steer-current.jsonl")
    mem.add(Candidate(
        id="current", design_id="gcd", parent_id=None, level="pdn", knobs={"source": "current_run"},
        knobs_fp="current", rtl_fp="rtl", netlist_fp=None, fidelity="F4",
        qor=QoR(dynamic_ir_mv=3.2, fidelity="F4"), cost_s=0.0,
    ))
    check(mem.get("current").qor.dynamic_ir_mv == 3.2, "steering reads the current candidate measurement")


if __name__ == "__main__":
    print("test_dse_steer is exercised by test_dse.py")

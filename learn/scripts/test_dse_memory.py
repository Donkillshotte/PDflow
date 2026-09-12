"""Current-invocation DesignMemory contracts.

The suite deliberately constructs its own run directory. No committed
campaign, launch ledger, or prior result is a test fixture.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from dse.experiments import Experiment, ExperimentLog
from dse.fingerprint import knobs_fp
from dse.memory import Candidate, DesignMemory
from dse.metrics import QoR


def check_memory(check, *, root: Path) -> dict:
    run_root = Path(tempfile.mkdtemp(prefix="dse-live-"))
    path = run_root / "memory.jsonl"
    mem = DesignMemory(path)
    parent = mem.add(
        Candidate(
            id="parent",
            design_id="gcd",
            parent_id=None,
            level="logic",
            knobs={"name": "current"},
            knobs_fp=knobs_fp("logic", {"name": "current"}),
            rtl_fp="rtl-current",
            netlist_fp=None,
            fidelity="F1",
            qor=QoR(area_um2=100.0, fidelity="F1"),
            cost_s=0.0,
        )
    )
    child = mem.add(
        Candidate(
            id="child",
            design_id="gcd",
            parent_id=parent.id,
            level="physical",
            knobs={"source": "current_run"},
            knobs_fp=knobs_fp("physical", {"source": "current_run"}),
            rtl_fp="rtl-current",
            netlist_fp=None,
            fidelity="F2",
            qor=QoR(congestion=0.2, fidelity="F2"),
            cost_s=1.0,
        )
    )
    reloaded = DesignMemory(path)
    check(len(reloaded) == 2, "current memory reloads its own rows")
    check(reloaded.get(child.id).parent_id == parent.id, "current parent lineage survives reload")
    check(reloaded.get(child.id).design_id == "gcd", "current design identity survives reload")

    log = ExperimentLog(run_root / "explicit.jsonl")
    log.append(
        Experiment(
            id="run-a",
            phase="test",
            design="gcd",
            clock_ns=0.46,
            variant="live_test",
            role="test",
            status="ok",
        )
    )
    check(log.path.is_file(), "explicit current experiment log is written")
    check(log.path == run_root / "explicit.jsonl", "explicit log stays in the requested run directory")
    return {"mem": mem, "mem2": reloaded, "root": root}


if __name__ == "__main__":
    print("test_dse_memory is exercised by test_dse.py")

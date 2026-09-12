#!/usr/bin/env python3
"""Contract tests for checkpoint-aware analysis eligibility."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn"))

from pdflow_agent.eligibility import check_policy, evaluate_check  # noqa: E402


@dataclass
class FakeArtifact:
    relative_path: str
    authority: str = "finish"
    variant: str = "flowlab"
    mtime_ns: int = 0

    def __post_init__(self) -> None:
        if not self.mtime_ns:
            self.mtime_ns = time.time_ns()

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": "artifact-test",
            "kind": "odb",
            "scope": "flow",
            "variant": self.variant,
            "relative_path": self.relative_path,
            "content_hash": "test-hash",
            "size": 1,
            "mtime_ns": self.mtime_ns,
            "revision": 0,
            "producer": "test",
            "run_id": None,
            "authority": self.authority,
            "mutable": self.authority == "candidate",
        }


class FakeCatalog:
    def __init__(self, *artifacts: FakeArtifact) -> None:
        self.artifacts = list(artifacts)
        self.list_calls = 0

    def list(self, **_: object) -> list[FakeArtifact]:
        self.list_calls += 1
        return list(self.artifacts)


def tools(*missing: str) -> list[dict[str, object]]:
    missing_set = set(missing)
    return [
        {
            "tool_id": tool_id,
            "availability": "MISSING" if tool_id in missing_set else "READY",
        }
        for tool_id in ("openroad", "opensta", "klayout", "ngspice", "xyce", "vyges_em_ir")
    ]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL " + message)
    print("ok  " + message)


def main() -> int:
    repo = ROOT
    floorplan = FakeArtifact(
        "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/2_4_floorplan_pdn.odb"
    )
    place = FakeArtifact(
        "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/3_5_place_dp.odb"
    )
    route = FakeArtifact(
        "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/5_2_route.odb"
    )

    result = evaluate_check(
        repo,
        FakeCatalog(floorplan),
        check_id="gridcheck",
        stage="floorplan",
        variant="flowlab",
        tools=tools(),
    )
    check(result["eligible"] is True, "gridcheck is eligible at floorplan")
    check(result["evidence_class"] == "CHECKPOINT_EVIDENCE", "floorplan gridcheck is checkpoint evidence")

    result = evaluate_check(
        repo,
        FakeCatalog(floorplan),
        check_id="gridcheck",
        stage="synth",
        variant="flowlab",
        tools=tools(),
    )
    check(result["eligible"] is False, "gridcheck is not eligible before a physical checkpoint")
    check(result["status"] == "GAP", "ineligible gridcheck is GAP, never PASS")

    result = evaluate_check(
        repo,
        FakeCatalog(floorplan),
        check_id="static_ir",
        stage="floorplan",
        variant="flowlab",
        tools=tools(),
    )
    check(result["eligible"] is False, "static IR is not exposed at floorplan")

    result = evaluate_check(
        repo,
        FakeCatalog(place),
        check_id="static_ir",
        stage="place",
        variant="flowlab",
        tools=tools(),
    )
    check(result["eligible"] is True, "static IR is eligible at placement")
    check(result["evidence_class"] == "PROXY", "placement IR is explicitly proxy evidence")

    result = evaluate_check(
        repo,
        FakeCatalog(route),
        check_id="power_grid_em",
        stage="route",
        variant="flowlab",
        tools=tools(),
    )
    check(result["eligible"] is True, "power-grid EM has a native adapter at route")
    check(result["action"] == "power_grid_em", "power-grid EM uses its explicit action")
    check(result["evidence_class"] == "PROXY", "power-grid EM cannot be promoted to signoff")

    result = evaluate_check(
        repo,
        FakeCatalog(place),
        check_id="dynamic_ir",
        stage="place",
        variant="flowlab",
        tools=tools(),
    )
    dynamic_mode = result["knob_schema"]["mode"]
    check(
        dynamic_mode["options"] == ["clock", "spatial", "simultaneous"],
        "Dynamic IR publishes its adapter-specific modes",
    )
    check(dynamic_mode["default"] == "clock", "Dynamic IR defaults to clock mode")

    result = evaluate_check(
        repo,
        FakeCatalog(place),
        check_id="signal_em",
        stage="route",
        variant="flowlab",
        tools=tools(),
    )
    check(result["eligible"] is False, "signal EM stays unavailable without its dedicated engine")
    check(any("signal_em_engine" in item for item in result["missing"]), "signal EM explains the missing capability")

    result = evaluate_check(
        repo,
        FakeCatalog(),
        check_id="system_pdn",
        stage="package",
        variant="lab_asap7_gcd_tc_rvt_nldm_7p5",
        tools=tools("ngspice", "xyce"),
    )
    check(result["eligible"] is False, "system PDN is blocked when both SPICE engines are absent")
    check(result["status"] == "GAP", "missing SPICE engine is reported as GAP")

    result = evaluate_check(
        repo,
        FakeCatalog(),
        check_id="system_pdn",
        stage="package",
        variant="lab_asap7_gcd_tc_rvt_nldm_7p5",
        tools=tools(),
    )
    check(result["eligible"] is True, "system PDN becomes eligible with a native SPICE engine")

    # A report that contains valid provenance but fails a requirement must
    # remain visible as valid evidence, never collapse into a generic process
    # failure or a false PASS.
    with TemporaryDirectory(prefix="pdflow-eligibility-") as raw_tmp:
        tmp = Path(raw_tmp)
        report_dir = tmp / "learn" / "sim" / "reports"
        report_dir.mkdir(parents=True)
        report = report_dir / "gridcheck_flowlab_floorplan.json"
        report.write_text(
            json.dumps(
                {
                    "status": "FAIL",
                    "ok": False,
                    "checkpoint_artifact": floorplan.relative_path,
                    "nets": {"VDD": {"connected": False}, "VSS": {"connected": True}},
                }
            )
        )
        report_result = evaluate_check(
            tmp,
            FakeCatalog(floorplan),
            check_id="gridcheck",
            stage="floorplan",
            variant="flowlab",
            tools=tools(),
        )
        check(report_result["status"] == "FAIL", "checkpoint report requirement failure is preserved")
    check(report_result["evidence_status"] == "PASS", "failed checkpoint result remains valid evidence")
    check(report_result["requirement_status"] == "FAIL", "checkpoint requirement status is separate")

    # A full policy contains several checks, but all of them must consume one
    # scoped artifact snapshot. Repeating a recursive ORFS scan per check made
    # the read-only preflight appear hung on a populated ASAP7 workspace.
    snapshot_catalog = FakeCatalog(floorplan)
    policy = check_policy(
        repo,
        snapshot_catalog,
        stage="floorplan",
        variant="flowlab",
        tools=tools(),
    )
    check(len(policy["checks"]) == 9, "policy publishes the complete checkpoint matrix")
    check(snapshot_catalog.list_calls == 1, "policy evaluates every check from one artifact snapshot")

    print("ALL test_analysis_eligibility PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

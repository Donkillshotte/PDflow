"""Contract and localhost API tests for the PDflow local agent."""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_TEST_POLL_TIMEOUT_S = float(os.environ.get("PD_FLOW_TEST_POLL_TIMEOUT_S", "30"))
sys.path.insert(0, str(ROOT / "learn"))

from pdflow_agent.agent import LocalAgent
from pdflow_agent.artifacts import ArtifactCatalog
from pdflow_agent.contracts import (
    finish_authority,
    validate_artifact,
    validate_action_descriptor,
    validate_report,
    validate_run,
    validate_tool_descriptor,
)

def request(
    base: str,
    path: str,
    method: str = "GET",
    payload: dict | None = None,
) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        base + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def request_error(
    base: str,
    path: str,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[int, dict]:
    """Return the HTTP status and JSON body for an expected error response."""

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        base + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as response:
        return response.code, json.loads(response.read().decode("utf-8"))


def main() -> None:
    assert finish_authority(
        ".pdflow/runs/run-12345678/candidate/6_final.odb"
    ) == ("candidate", True)
    assert finish_authority(
        "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb"
    ) == ("finish", False)
    assert validate_run(
        {
            "run_id": "run-12345678",
            "surface": "flow",
            "input_artifacts": [],
        }
    ) == []

    with tempfile.TemporaryDirectory(prefix="pdflow-agent-") as temp:
        repo = Path(temp)
        shutil.copytree(ROOT / "config", repo / "config")
        actions_manifest = repo / "config/pdflow/action_registry.json"
        actions = json.loads(actions_manifest.read_text(encoding="utf-8"))
        actions["actions"].extend(
            [
                {
                    "action_id": "unit_action",
                    "display_name": "Unit action",
                    "surface": "flow",
                    "command": ["bash", "{repo}/learn/scripts/unit_action.sh"],
                    "timeout_seconds": 600,
                    "required_tools": [],
                    "mutates": False,
                },
                {
                    "action_id": "missing_dependency",
                    "display_name": "Missing dependency",
                    "surface": "lab",
                    "command": ["bash", "{repo}/learn/scripts/unit_action.sh"],
                    "timeout_seconds": 600,
                    "required_tools": ["does-not-exist"],
                    "mutates": False,
                },
                {
                    "action_id": "unit_report",
                    "display_name": "Unit report",
                    "surface": "package",
                    "command": ["bash", "{repo}/learn/scripts/unit_report.sh"],
                    "timeout_seconds": 600,
                    "required_tools": [],
                    "mutates": False,
                },
                {
                    "action_id": "unit_sleep",
                    "display_name": "Unit timeout",
                    "surface": "lab",
                    "command": ["bash", "{repo}/learn/scripts/unit_sleep.sh"],
                    "timeout_seconds": 600,
                    "required_tools": [],
                    "mutates": False,
                },
                {
                    "action_id": "unit_refused",
                    "display_name": "Unit controlled refusal",
                    "surface": "lab",
                    "command": ["bash", "{repo}/learn/scripts/unit_refused.sh"],
                    "timeout_seconds": 600,
                    "required_tools": [],
                    "mutates": False,
                },
            ]
        )
        actions_manifest.write_text(json.dumps(actions), encoding="utf-8")
        scripts = repo / "learn/scripts"
        scripts.mkdir(parents=True)
        unit_action = scripts / "unit_action.sh"
        unit_action.write_text(
            "#!/bin/sh\nprintf 'UNIT_ACTION_OK\\n'\n",
            encoding="utf-8",
        )
        unit_action.chmod(unit_action.stat().st_mode | stat.S_IXUSR)
        unit_report = scripts / "unit_report.sh"
        unit_report.write_text(
            "#!/bin/sh\nmkdir -p learn/sim/reports\nprintf '%s\\n' '{\"status\":\"GAP\",\"ok\":false,\"reason\":\"fixture dependency missing\"}' > learn/sim/reports/unit_report_flowlab.json\n",
            encoding="utf-8",
        )
        unit_report.chmod(unit_report.stat().st_mode | stat.S_IXUSR)
        unit_sleep = scripts / "unit_sleep.sh"
        unit_sleep.write_text("#!/bin/sh\nsleep 2\n", encoding="utf-8")
        unit_sleep.chmod(unit_sleep.stat().st_mode | stat.S_IXUSR)
        unit_refused = scripts / "unit_refused.sh"
        unit_refused.write_text(
            "#!/bin/sh\nprintf '%s\\n' 'REFUSED: protected fixture finish' >&2\nexit 2\n",
            encoding="utf-8",
        )
        unit_refused.chmod(unit_refused.stat().st_mode | stat.S_IXUSR)
        source = (
            repo
            / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab"
        )
        source.mkdir(parents=True)
        base = repo / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/base"
        base.mkdir(parents=True)
        (base / "6_final.odb").write_bytes(b"BASE ODB fixture\n")
        odb = source / "6_final.odb"
        odb.write_bytes(b"ODB fixture\n")
        floorplan_odb = source / "2_4_floorplan_pdn.odb"
        floorplan_odb.write_bytes(b"FLOORPLAN ODB fixture\n")

        fake = repo / "fake-openroad"
        fake.write_text("#!/bin/sh\nprintf 'fake-openroad\\n'\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        old_env = {
            key: os.environ.get(key)
            for key in ("OPENROAD_BIN", "DISPLAY")
        }
        os.environ["OPENROAD_BIN"] = str(fake)
        os.environ["DISPLAY"] = ":99"
        try:
            catalog = ArtifactCatalog(repo)
            stage_env = LocalAgent._flowlab_stage_environment(
                {
                    "parameters": {
                        "coreUtilization": 40,
                        "placeDensityAddon": 0.25,
                        "abcArea": 1,
                        "sdcPreset": "relaxed",
                        "tnsEndPercent": 90,
                    }
                }
            )
            assert stage_env["CORE_UTILIZATION"] == "40"
            assert stage_env["SDC_FILE"].endswith("constraint_relaxed.sdc")
            analysis_env = LocalAgent._analysis_checkpoint_environment(
                {
                    "parameters": {
                        "checkpoint": "route",
                        "peak_factor": 10,
                        "ir_limit_pct": 4.5,
                        "c_decap": "5e-14",
                        "switch_t_ns": 1.2,
                        "switch_dur_ns": 0.08,
                        "package_resistance": 0.05,
                    }
                },
                "power_grid_em",
            )
            assert analysis_env["PD_FLOW_CHECKPOINT"] == "route"
            assert analysis_env["PEAK_FACTOR"] == "10"
            assert analysis_env["IR_LIMIT_PCT"] == "4.5"
            assert analysis_env["C_DECAP"] == "5e-14"
            assert analysis_env["SWITCH_DUR_NS"] == "0.08"
            try:
                LocalAgent._analysis_checkpoint_environment(
                    {"parameters": {"checkpoint": "route", "coreUtilization": 40}},
                    "power_grid_em",
                )
            except ValueError:
                pass
            else:
                raise AssertionError("FlowLab recook parameter leaked into analysis")
            try:
                LocalAgent._analysis_checkpoint_environment(
                    {"parameters": {"checkpoint": "route", "peak_factor": 99}},
                    "power_grid_em",
                )
            except ValueError:
                pass
            else:
                raise AssertionError("out-of-range analysis parameter accepted")
            try:
                LocalAgent._flowlab_stage_environment(
                    {"parameters": {"coreUtilization": 99}}
                )
            except ValueError:
                pass
            else:
                raise AssertionError("out-of-range FlowLab parameter accepted")
            source_ref = catalog.resolve_path(
                "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb"
            )
            assert source_ref is not None
            assert source_ref.authority == "finish"
            assert source_ref.mutable is False
            assert validate_artifact(source_ref.to_dict()) == []
            floorplan_ref = catalog.resolve_path(
                "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/2_4_floorplan_pdn.odb"
            )
            assert floorplan_ref is not None
            assert floorplan_ref.authority == "finish"
            assert floorplan_ref.mutable is False
            assert validate_artifact(floorplan_ref.to_dict()) == []
            invalid_finish = source_ref.to_dict()
            invalid_finish["mutable"] = True
            assert validate_artifact(invalid_finish)

            agent = LocalAgent(repo_root=repo, port=0, poll_seconds=0.25)
            server = agent.start()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            health = request(base, "/health")
            assert health["service"] == "pdflow-local-agent"
            assert health["resources"]["available"] is True
            assert health["resources"]["limits"]["memory_max_bytes"] == 6 * 1024**3
            assert health["resources"]["limits"]["max_full_pressure_avg10"] == 10.0
            registry = request(base, "/v1/registry")
            assert all(validate_tool_descriptor(tool) == [] for tool in registry["tools"])
            assert all(validate_action_descriptor(action) == [] for action in registry["actions"])
            assert any(tool["tool_id"] == "openroad" for tool in registry["tools"])
            assert any(
                action["action_id"] == "unit_action"
                and action["availability"] == "READY"
                for action in registry["actions"]
            )
            package = request(base, "/v1/package")
            assert package["status"] == "GAP"
            assert package["ok"] is False
            assert package["evidence_ok"] is False
            assert package["manifest"] is None
            assert package["steps"]["system_pdn"]["status"] in {"GAP", "NOT_RUN"}
            ledger = request(base, "/v1/path-ledger")
            assert ledger["status"] in {"GAP", "NOT_RUN", "FAIL"}
            assert ledger["ok"] is False
            missing_action = request(
                base,
                "/v1/jobs",
                "POST",
                {
                    "action": "missing_dependency",
                    "operation": "action",
                    "run_id": "run-missing-dependency",
                },
            )
            assert missing_action["state"] == "GAP"
            assert "does-not-exist" in missing_action["reason"]
            run = request(base, "/v1/runs", "POST", {"surface": "flow"})["run"]
            assert Path(run["run_dir"]).name == run["run_id"]
            unknown_status, unknown_candidate = request_error(
                base,
                "/v1/candidates",
                "POST",
                {
                    "run_id": "run-unknown-candidate",
                    "artifact_id": source_ref.artifact_id,
                },
            )
            assert unknown_status == 400
            assert unknown_candidate.get("error") == "candidate references an unknown PDflow run"
            candidate = request(
                base,
                "/v1/candidates",
                "POST",
                {
                    "run_id": run["run_id"],
                    "artifact_id": source_ref.artifact_id,
                },
            )["candidate"]
            assert candidate["authority"] == "candidate"
            assert candidate["mutable"] is True

            job = request(
                base,
                "/v1/jobs",
                "POST",
                {
                    "tool_id": "openroad",
                    "operation": "gui",
                    "artifact_id": source_ref.artifact_id,
                    "run_id": run["run_id"],
                    "mode": "view",
                    "timeout_seconds": 10,
                },
            )
            assert job["state"] == "QUEUED"
            deadline = time.time() + AGENT_TEST_POLL_TIMEOUT_S
            final = job
            while time.time() < deadline:
                final = request(base, f"/v1/jobs?id={job['job_id']}")
                if final["state"] not in {"QUEUED", "RUNNING"}:
                    break
                time.sleep(0.05)
            assert final["state"] == "COMPLETED", final
            assert final["report"]["ok"] is True
            assert final["termination_cause"] is None
            assert final["resource"]["cgroup"], final
            assert final["report"]["resource"]["cgroup"] == final["resource"]["cgroup"]
            assert validate_report(final["report"]) == []

            edit_job = request(
                base,
                "/v1/jobs",
                "POST",
                {
                    "tool_id": "openroad",
                    "operation": "gui",
                    "artifact_id": floorplan_ref.artifact_id,
                    "run_id": run["run_id"],
                    "mode": "edit",
                    "timeout_seconds": 10,
                },
            )
            edit_final = edit_job
            deadline = time.time() + AGENT_TEST_POLL_TIMEOUT_S
            while time.time() < deadline:
                edit_final = request(base, f"/v1/jobs?id={edit_job['job_id']}")
                if edit_final["state"] not in {"QUEUED", "RUNNING"}:
                    break
                time.sleep(0.05)
            assert edit_final["state"] == "COMPLETED", edit_final
            assert edit_final["artifact"]["authority"] == "candidate", edit_final
            assert edit_final["artifact"]["mutable"] is True, edit_final
            assert "/candidate/orfs/results/" in edit_final["artifact"]["relative_path"]
            assert floorplan_odb.read_bytes() == b"FLOORPLAN ODB fixture\n"
            detail = request(
                base,
                "/v1/artifacts/" + source_ref.artifact_id,
            )
            assert detail["artifact"]["authority"] == "finish"
            assert detail["read_only"] is True

            action_job = request(
                base,
                "/v1/jobs",
                "POST",
                {
                    "action": "unit_action",
                    "operation": "action",
                    "run_id": run["run_id"],
                    "variant": "flowlab",
                },
            )
            action_final = action_job
            deadline = time.time() + AGENT_TEST_POLL_TIMEOUT_S
            while time.time() < deadline:
                action_final = request(base, f"/v1/jobs?id={action_job['job_id']}")
                if action_final["state"] not in {"QUEUED", "RUNNING"}:
                    break
                time.sleep(0.05)
            assert action_final["state"] == "COMPLETED", action_final
            assert action_final["report"]["scope"] == "flow"
            assert action_final["report"]["tool_versions"] == {}
            report_id = action_final["report"]["report_id"]
            assert request(base, "/v1/reports/" + report_id)["report_id"] == report_id

            report_job = request(
                base,
                "/v1/jobs",
                "POST",
                {
                    "action": "unit_report",
                    "operation": "action",
                    "run_id": run["run_id"],
                    "variant": "flowlab",
                },
            )
            report_final = report_job
            deadline = time.time() + AGENT_TEST_POLL_TIMEOUT_S
            while time.time() < deadline:
                report_final = request(base, f"/v1/jobs?id={report_job['job_id']}")
                if report_final["state"] not in {"QUEUED", "RUNNING"}:
                    break
                time.sleep(0.05)
            assert report_final["state"] == "COMPLETED"
            assert report_final["report"]["status"] == "GAP"
            assert report_final["report"]["ok"] is False
            assert report_final["report"]["product_signoff"] is False
            assert "fixture dependency missing" in report_final["report"]["reason"]

            refusal_job = request(
                base,
                "/v1/jobs",
                "POST",
                {
                    "action": "unit_refused",
                    "operation": "action",
                    "run_id": run["run_id"],
                    "variant": "flowlab",
                },
            )
            refusal_final = refusal_job
            deadline = time.time() + AGENT_TEST_POLL_TIMEOUT_S
            while time.time() < deadline:
                refusal_final = request(base, f"/v1/jobs?id={refusal_job['job_id']}")
                if refusal_final["state"] not in {"QUEUED", "RUNNING"}:
                    break
                time.sleep(0.05)
            assert refusal_final["state"] == "GAP", refusal_final
            assert refusal_final["termination_cause"] == "refused", refusal_final
            assert refusal_final["report"]["status"] == "GAP", refusal_final
            assert refusal_final["report"]["termination_cause"] == "refused", refusal_final
            assert "protected fixture finish" in refusal_final["reason"], refusal_final

            timeout_job = request(
                base,
                "/v1/jobs",
                "POST",
                {
                    "action": "unit_sleep",
                    "operation": "action",
                    "run_id": run["run_id"],
                    "variant": "flowlab",
                    "timeout_seconds": 1,
                },
            )
            timeout_final = timeout_job
            deadline = time.time() + AGENT_TEST_POLL_TIMEOUT_S
            while time.time() < deadline:
                timeout_final = request(base, f"/v1/jobs?id={timeout_job['job_id']}")
                if timeout_final["state"] not in {"QUEUED", "RUNNING"}:
                    break
                time.sleep(0.05)
            assert timeout_final["state"] == "FAILED"
            assert "timeout after 1s" in timeout_final["reason"]
            assert timeout_final["termination_cause"] == "timeout"
            assert timeout_final["report"]["termination_cause"] == "timeout"

            cancel_job = request(
                base,
                "/v1/jobs",
                "POST",
                {
                    "action": "unit_sleep",
                    "operation": "action",
                    "run_id": run["run_id"],
                    "variant": "flowlab",
                    "timeout_seconds": 10,
                },
            )
            time.sleep(0.1)
            cancelled = request(
                base,
                f"/v1/jobs/{cancel_job['job_id']}/cancel",
                "POST",
            )
            assert cancelled["state"] in {"QUEUED", "RUNNING", "CANCELLED"}
            cancel_final = cancelled
            deadline = time.time() + AGENT_TEST_POLL_TIMEOUT_S
            while time.time() < deadline:
                cancel_final = request(base, f"/v1/jobs?id={cancel_job['job_id']}")
                if cancel_final["state"] not in {"QUEUED", "RUNNING"}:
                    break
                time.sleep(0.05)
            assert cancel_final["state"] == "CANCELLED", cancel_final
            assert cancel_final["termination_cause"] == "cancelled", cancel_final
            assert cancel_final["resource"]["resource_cause"] is None, cancel_final
            assert cancel_final["report"]["status"] == "PARTIAL", cancel_final
            assert cancel_final["report"]["ok"] is False, cancel_final

            # Candidate outputs preserve the ORFS results subtree so the same
            # stage-relative artifact names resolve in the agent, Studio API,
            # and native tool launchers. Use the path returned by the contract
            # instead of reconstructing the legacy flat candidate location.
            candidate_path = repo / candidate["relative_path"]
            deadline = time.time() + min(AGENT_TEST_POLL_TIMEOUT_S, 10)
            while time.time() < deadline:
                candidate_ref = next(
                    (
                        item
                        for item in request(
                            base,
                            "/v1/artifacts?authority=candidate",
                        )["artifacts"]
                        if item["relative_path"]
                        == str(candidate_path.relative_to(repo))
                    ),
                    None,
                )
                if candidate_ref:
                    break
                time.sleep(0.1)
            time.sleep(0.7)
            candidate_path.write_bytes(b"candidate update\n")
            deadline = time.time() + min(AGENT_TEST_POLL_TIMEOUT_S, 10)
            candidate_ref = None
            while time.time() < deadline:
                candidate_ref = next(
                    (
                        item
                        for item in request(
                            base,
                            "/v1/artifacts?authority=candidate",
                        )["artifacts"]
                        if item["relative_path"]
                        == str(candidate_path.relative_to(repo))
                    ),
                    None,
                )
                if candidate_ref and candidate_ref["revision"] >= 1:
                    break
                time.sleep(0.1)
            assert candidate_ref is not None
            assert candidate_ref["revision"] >= 1

            refused_batch = request(
                base,
                "/v1/jobs",
                "POST",
                {
                    "tool_id": "openroad",
                    "operation": "batch",
                    "artifact_id": source_ref.artifact_id,
                },
            )
            assert refused_batch["state"] == "GAP"
            assert "allowlisted PDflow action" in refused_batch["reason"]
            compare = agent.compare_reports(
                {
                    "left": {
                        "run_id": run["run_id"],
                        "mesh_id": "mesh",
                        "oracle": "live",
                        "input_artifact_refs": [
                            {
                                "artifact_id": "artifact-12345678",
                                "content_hash": "a",
                                "revision": 0,
                                "relative_path": "a.odb",
                            }
                        ],
                        "metrics": {"wns": -1.0},
                    },
                    "right": {
                        "run_id": run["run_id"],
                        "mesh_id": "mesh",
                        "oracle": "live",
                        "input_artifact_refs": [
                            {
                                "artifact_id": "artifact-12345678",
                                "content_hash": "a",
                                "revision": 0,
                                "relative_path": "a.odb",
                            }
                        ],
                        "metrics": {"wns": -0.5},
                    },
                }
            )
            assert compare["status"] == "PROXY"
            assert compare["comparison_scope"] == "same-live-invocation"
            assert agent.compare_reports(
                {
                    "left": {"run_id": "run-12345678"},
                    "right": {"run_id": "run-87654321"},
                }
            )["comparison_scope"] == "not-comparable"
            agent.stop()
            server.shutdown()
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    print("OK test_pdflow_agent")


if __name__ == "__main__":
    main()

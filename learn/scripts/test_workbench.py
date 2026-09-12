"""Unit tests for the explicit Analysis Workbench preflight contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn"))

from pdflow_agent.workbench import build_bundle_plan, selected_check_ids


def check(
    check_id: str,
    *,
    action: str | None,
    eligible: bool = True,
    cost_class: str = "light",
    missing: list[str] | None = None,
) -> dict:
    return {
        "check_id": check_id,
        "display_name": check_id,
        "action": action,
        "eligible": eligible,
        "status": "NOT_RUN",
        "evidence_class": "CHECKPOINT_EVIDENCE",
        "execution_class": "NATIVE_JOB" if action else "EVIDENCE_ONLY",
        "cost_class": cost_class,
        "estimated_duration_seconds": 30,
        "resource_limit": {"timeout_seconds": 600},
        "missing": missing or [],
        "warnings": [],
        "downstream_invalidations": [check_id],
        "report_file": None,
        "default_trigger": "on-stage-success",
    }


def main() -> None:
    policy = {
        "stage": "finish",
        "variant": "flowlab",
        "run_id": None,
        "checks": [
            check("gridcheck", action="gridcheck"),
            check("sta", action="sta_checkpoint", cost_class="medium"),
            check("drc", action="drc_signoff"),
            check("signal_em", action=None, eligible=False, missing=["engine missing"]),
        ],
    }
    actions = [
        {"action_id": "gridcheck", "availability": "READY", "timeout_seconds": 600},
        {"action_id": "sta_checkpoint", "availability": "READY", "timeout_seconds": 600},
        {"action_id": "drc_signoff", "availability": "READY", "timeout_seconds": 600},
    ]

    assert selected_check_ids("recommended", policy) == ["gridcheck", "sta", "drc"]
    recommended = build_bundle_plan(
        bundle_id="recommended",
        policy=policy,
        action_registry=actions,
    )
    assert recommended["ready"] is True
    assert recommended["read_only"] is True
    assert recommended["confirmation_required"] is True
    assert recommended["resource_limit"]["timeout_seconds"] == 600
    assert set(recommended["downstream_invalidations"]) == {"gridcheck", "sta", "drc"}

    evidence_only_policy = {
        "stage": "floorplan",
        "variant": "flowlab",
        "run_id": None,
        "checks": [
            check("gridcheck", action="gridcheck"),
            {
                **check("drc", action=None),
                "execution_class": "EVIDENCE_ONLY",
            },
        ],
    }
    evidence_only = build_bundle_plan(
        bundle_id="recommended",
        policy=evidence_only_policy,
        action_registry=actions,
    )
    assert evidence_only["ready"] is True
    assert evidence_only["jobs"][1]["runnable"] is False
    assert "evidence-only" in evidence_only["jobs"][1]["reason"]

    blocked_policy = {
        "stage": "finish",
        "variant": "lab_asap7_gcd_tc_rvt_nldm_7p5_320ps",
        "run_id": None,
        "checks": [
            check("gridcheck", action="gridcheck", eligible=False, missing=["finish ODB is missing"]),
            check("sta", action="sta_checkpoint", eligible=False, missing=["finish ODB is missing"]),
        ],
    }
    # A recommended preflight remains a displayable blocked plan when no
    # default-trigger check is currently runnable; it must not become a 500.
    assert selected_check_ids("recommended", blocked_policy) == ["gridcheck", "sta"]
    blocked = build_bundle_plan(
        bundle_id="recommended",
        policy=blocked_policy,
        action_registry=actions,
    )
    assert blocked["ready"] is False
    assert all(item["runnable"] is False for item in blocked["jobs"])
    assert all(item["missing"] for item in blocked["jobs"])

    power = build_bundle_plan(
        bundle_id="final_power_integrity",
        policy=policy,
        action_registry=actions,
    )
    assert power["ready"] is False
    assert all(not item["runnable"] for item in power["jobs"])
    assert power["jobs"][0]["status"] == "GAP"

    missing_action = build_bundle_plan(
        bundle_id="product_signoff",
        policy=policy,
        action_registry=actions[:2],
    )
    assert missing_action["ready"] is False
    assert any("not present" in item["reason"] for item in missing_action["jobs"])
    print("OK test_workbench")


if __name__ == "__main__":
    main()

"""Analysis Workbench planning primitives.

The workbench deliberately separates planning from execution.  A bundle
preview only reads checkpoint policy and the native registry; the caller must
explicitly confirm the returned plan before jobs are submitted.  Keeping this
logic in the agent prevents React routes from growing a second copy of stage
policy and makes the same preflight available to the desktop shell, scripts,
and tests.
"""

from __future__ import annotations

from typing import Any


BUNDLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "recommended": {
        "label": "Recommended checkpoint checks",
        "description": "Lightweight and timing checks appropriate for the selected checkpoint.",
        "checks": None,
        "trigger": "on-stage-success",
    },
    "final_timing": {
        "label": "Final timing",
        "description": "Setup/hold timing evidence for the selected checkpoint.",
        "checks": ["sta"],
        "trigger": "manual",
    },
    "final_power_integrity": {
        "label": "Final power integrity",
        "description": "Static IR, dynamic IR, and power-grid EM evidence when eligible.",
        "checks": ["static_ir", "dynamic_ir", "power_grid_em"],
        "trigger": "manual",
    },
    "gds_verification": {
        "label": "GDS verification",
        "description": "Physical DRC and LVS evidence for the final layout.",
        "checks": ["drc", "lvs"],
        "trigger": "manual",
    },
    "product_signoff": {
        "label": "Product signoff prerequisites",
        "description": "Current Product checks only; Package and Lab evidence remain separate.",
        "checks": ["sta", "drc", "lvs"],
        "trigger": "signoff-bundle",
    },
    "package_system_pdn": {
        "label": "Package System PDN",
        "description": "VRM-to-board-to-package-to-die simulation in the Package scope.",
        "checks": ["system_pdn"],
        "trigger": "manual",
    },
}


def bundle_definition(bundle_id: str) -> dict[str, Any]:
    value = BUNDLE_DEFINITIONS.get(str(bundle_id))
    if value is None:
        raise ValueError(f"unknown analysis bundle: {bundle_id}")
    return {
        "bundle_id": str(bundle_id),
        "label": str(value["label"]),
        "description": str(value["description"]),
        "checks": list(value["checks"]) if value["checks"] is not None else None,
        "trigger": str(value["trigger"]),
    }


def selected_check_ids(
    bundle_id: str,
    policy: dict[str, Any],
    requested: list[str] | None = None,
) -> list[str]:
    """Resolve and de-duplicate a user selection without changing policy."""

    definition = bundle_definition(bundle_id)
    if requested is not None:
        values = requested
    elif definition["checks"] is not None:
        values = definition["checks"]
    else:
        # Recommended means the checks explicitly declared as automatic
        # postconditions by the descriptor.  Heavy analyses remain opt-in.
        values = [
            item.get("check_id")
            for item in policy.get("checks", [])
            if isinstance(item, dict)
            and item.get("default_trigger") == "on-stage-success"
            and bool(item.get("eligible"))
        ]
        if not values:
            # A recommendation must remain inspectable even when the selected
            # checkpoint is not runnable (for example an uncooked ASAP7
            # profile or a missing ODB).  Returning the policy's blocked
            # checks lets the UI explain the missing prerequisite instead of
            # turning a valid preflight into an opaque HTTP 500.
            values = [
                item.get("check_id")
                for item in policy.get("checks", [])
                if isinstance(item, dict)
                and item.get("default_trigger") == "on-stage-success"
            ]
    result: list[str] = []
    for value in values:
        check_id = str(value or "")
        if check_id and check_id not in result:
            result.append(check_id)
    if not result:
        raise ValueError("analysis bundle contains no checks for this checkpoint")
    return result


def build_bundle_plan(
    *,
    bundle_id: str,
    policy: dict[str, Any],
    action_registry: list[dict[str, Any]],
    requested_check_ids: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, display-ready preflight plan.

    The function intentionally does not call ``build_action_command`` or
    inspect arbitrary paths.  It only consumes the already validated policy
    and action registry, so previewing a bundle cannot launch a process.
    """

    definition = bundle_definition(bundle_id)
    requested = selected_check_ids(bundle_id, policy, requested_check_ids)
    checks_by_id = {
        str(item.get("check_id")): item
        for item in policy.get("checks", [])
        if isinstance(item, dict) and item.get("check_id")
    }
    actions_by_id = {
        str(item.get("action_id")): item
        for item in action_registry
        if isinstance(item, dict) and item.get("action_id")
    }
    parameter_map = parameters if isinstance(parameters, dict) else {}
    jobs: list[dict[str, Any]] = []
    missing_checks: list[str] = []
    for check_id in requested:
        check = checks_by_id.get(check_id)
        if check is None:
            missing_checks.append(check_id)
            jobs.append(
                {
                    "check_id": check_id,
                    "eligible": False,
                    "runnable": False,
                    "status": "GAP",
                    "reason": "check is not published by the selected checkpoint policy",
                    "missing": ["unknown checkpoint check"],
                }
            )
            continue
        action_id = check.get("action")
        action = actions_by_id.get(str(action_id)) if action_id else None
        missing = [str(item) for item in check.get("missing", [])]
        warnings = [str(item) for item in check.get("warnings", [])]
        if action_id and action is None:
            missing.append(f"action is not present in the native action registry: {action_id}")
        if action and action.get("availability") != "READY":
            missing_tools = ", ".join(str(item) for item in action.get("missing_tools", []))
            missing.append(
                f"native action {action_id} is {action.get('availability')}"
                + (f" ({missing_tools})" if missing_tools else "")
            )
        runnable = bool(check.get("eligible") and action_id and not missing)
        reason = (
            missing[0]
            if missing
            else str(check.get("report_reason") or "")
            if not runnable
            else "ready to queue"
        )
        if (
            not runnable
            and bool(check.get("eligible"))
            and not missing
            and str(check.get("execution_class") or "") == "EVIDENCE_ONLY"
        ):
            reason = "evidence-only checkpoint; no native job is required"
        check_parameters = parameter_map.get(check_id, {})
        if not isinstance(check_parameters, dict):
            check_parameters = {}
        jobs.append(
            {
                "check_id": check_id,
                "display_name": check.get("display_name"),
                "action": action_id,
                "eligible": bool(check.get("eligible")),
                "runnable": runnable,
                "status": check.get("status", "NOT_RUN"),
                "evidence_class": check.get("evidence_class"),
                "execution_class": check.get("execution_class"),
                "cost_class": check.get("cost_class"),
                "estimated_duration_seconds": check.get("estimated_duration_seconds"),
                "timeout_seconds": (action or {}).get(
                    "timeout_seconds", (check.get("resource_limit") or {}).get("timeout_seconds", 600)
                ),
                "report_file": check.get("report_file"),
                "parameters": check_parameters,
                "missing": missing,
                "warnings": warnings,
                "invalidations": list(check.get("downstream_invalidations", [])),
                "reason": reason,
            }
        )

    runnable_jobs = [job for job in jobs if job.get("runnable")]
    estimated = sum(
        int(job.get("estimated_duration_seconds") or 0) for job in runnable_jobs
    )
    heavy = any(job.get("cost_class") == "heavy" for job in runnable_jobs)
    ready = bool(runnable_jobs) and not missing_checks and all(
        job.get("runnable")
        or (
            job.get("eligible")
            and not job.get("missing")
            and job.get("execution_class") == "EVIDENCE_ONLY"
        )
        for job in jobs
    )
    if not runnable_jobs:
        ready = False
    return {
        "schema_version": 1,
        "bundle_id": bundle_id,
        "label": definition["label"],
        "description": definition["description"],
        "trigger": definition["trigger"],
        "stage": policy.get("stage"),
        "variant": policy.get("variant"),
        "run_id": policy.get("run_id"),
        "check_ids": requested,
        "jobs": jobs,
        "ready": ready,
        "confirmation_required": heavy or len(runnable_jobs) > 1,
        "read_only": True,
        "estimated_duration_seconds": estimated,
        "resource_limit": {
            "queue": "single-heavy-slot" if heavy else "standard",
            "timeout_seconds": max(
                [int(job.get("timeout_seconds") or 600) for job in jobs] or [600]
            ),
        },
        "downstream_invalidations": sorted(
            {
                str(item)
                for job in jobs
                for item in job.get("invalidations", [])
            }
        ),
        "missing_checks": missing_checks,
        "principle": "preview is read-only; execution requires explicit confirmation and is submitted through the local-agent queue",
    }

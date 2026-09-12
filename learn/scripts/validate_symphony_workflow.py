#!/usr/bin/env python3
"""Validate PDflow's repository-owned Symphony workflow contract.

This validator is intentionally side-effect free. It checks the local
configuration and prompt policy, but it does not contact GitHub, start
Symphony, launch Codex, create a workspace, or run an EDA process.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_workflow(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read workflow: {exc}") from exc
    if not raw.startswith("---\n"):
        raise ValueError("workflow must start with YAML front matter")
    closing = raw.find("\n---\n", 4)
    if closing < 0:
        raise ValueError("workflow YAML front matter is not closed")
    front_matter = raw[4:closing]
    prompt = raw[closing + len("\n---\n") :].strip()
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on host packaging
        raise ValueError("PyYAML is required to validate WORKFLOW.md") from exc
    try:
        config = yaml.safe_load(front_matter)
    except yaml.YAMLError as exc:
        raise ValueError(f"workflow YAML is invalid: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError("workflow front matter must decode to a mapping")
    return config, prompt


def _mapping(value: Any, name: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{name} must be a mapping")
        return {}
    return value


def _non_empty_strings(value: Any, name: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not value:
        errors.append(f"{name} must be a non-empty list")
        return []
    result = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if len(result) != len(value):
        errors.append(f"{name} must contain only non-empty strings")
    return result


def validate(path: Path) -> list[str]:
    try:
        config, prompt = _load_workflow(path)
    except ValueError as exc:
        return [str(exc)]

    errors: list[str] = []
    tracker = _mapping(config.get("tracker"), "tracker", errors)
    provider = _mapping(tracker.get("provider"), "tracker.provider", errors)
    polling = _mapping(config.get("polling"), "polling", errors)
    workspace = _mapping(config.get("workspace"), "workspace", errors)
    hooks = _mapping(config.get("hooks"), "hooks", errors)
    agent = _mapping(config.get("agent"), "agent", errors)
    codex = _mapping(config.get("codex"), "codex", errors)

    if tracker.get("kind") != "github":
        errors.append("tracker.kind must be github for the PDflow adapter")
    if provider.get("repo") != "Donkillshotte/PDflow":
        errors.append("tracker.provider.repo must be Donkillshotte/PDflow")
    if provider.get("api_url") != "https://api.github.com":
        errors.append("tracker.provider.api_url must use the GitHub HTTPS API")
    labels = _non_empty_strings(
        tracker.get("required_labels"), "tracker.required_labels", errors
    )
    if "symphony" not in {label.lower() for label in labels}:
        errors.append("tracker.required_labels must include symphony as an opt-in gate")
    active = _non_empty_strings(tracker.get("active_states"), "tracker.active_states", errors)
    terminal = _non_empty_strings(
        tracker.get("terminal_states"), "tracker.terminal_states", errors
    )
    if {state.lower() for state in active} & {state.lower() for state in terminal}:
        errors.append("active and terminal tracker states must not overlap")

    if polling.get("interval_ms") != 30000:
        errors.append("polling.interval_ms must be 30000")
    if workspace.get("root") != "$PD_FLOW_SYMPHONY_WORKSPACE_ROOT":
        errors.append(
            "workspace.root must resolve through PD_FLOW_SYMPHONY_WORKSPACE_ROOT"
        )

    after_create = hooks.get("after_create")
    if not isinstance(after_create, str):
        errors.append("hooks.after_create must be a shell script")
    else:
        required_hook_fragments = (
            '"${PD_FLOW_REPO_ROOT:',
            'git -C "$PD_FLOW_REPO_ROOT"',
            "git clone --local --no-hardlinks --no-tags",
            'cp "$PD_FLOW_REPO_ROOT/WORKFLOW.md" ./WORKFLOW.md',
        )
        for fragment in required_hook_fragments:
            if fragment not in after_create:
                errors.append(f"hooks.after_create is missing {fragment}")
    if hooks.get("before_run") != "    set -eu\n    test -f AGENTS.md\n    test -f WORKFLOW.md\n":
        # YAML block scalar indentation is normalized by PyYAML. Keep this
        # policy check structural rather than accepting arbitrary hooks.
        before_run = hooks.get("before_run")
        if not isinstance(before_run, str) or "test -f AGENTS.md" not in before_run:
            errors.append("hooks.before_run must verify AGENTS.md")

    max_agents = agent.get("max_concurrent_agents")
    if not isinstance(max_agents, int) or not 1 <= max_agents <= 3:
        errors.append("agent.max_concurrent_agents must be an integer from 1 to 3")
    max_turns = agent.get("max_turns")
    if not isinstance(max_turns, int) or not 1 <= max_turns <= 16:
        errors.append("agent.max_turns must be an integer from 1 to 16")
    if agent.get("max_retry_backoff_ms") != 300000:
        errors.append("agent.max_retry_backoff_ms must be 300000")

    if codex.get("command") != "codex app-server":
        errors.append("codex.command must be exactly codex app-server")
    if codex.get("approval_policy") in {None, "never"}:
        errors.append("codex.approval_policy must require approval for risky requests")
    if codex.get("thread_sandbox") != "workspace-write":
        errors.append("codex.thread_sandbox must be workspace-write")
    for key, minimum in (("turn_timeout_ms", 600000), ("read_timeout_ms", 1000), ("stall_timeout_ms", 1000)):
        value = codex.get(key)
        if not isinstance(value, int) or value < minimum:
            errors.append(f"codex.{key} must be an integer >= {minimum}")

    forbidden = (
        "git reset --hard",
        "git checkout --",
        "pkill -f",
        "rm -rf",
        "docker",
    )
    # The prompt is expected to name forbidden operations as safety rules.
    # Inspect executable hook bodies only; mentioning a command in prose must
    # not make the workflow invalid.
    hook_text = "\n".join(
        value for value in hooks.values() if isinstance(value, str)
    ).lower()
    for fragment in forbidden:
        if fragment in hook_text:
            errors.append(f"workflow contains forbidden operation: {fragment}")
    prompt_requirements = (
        "./scripts/run_resource_job.sh",
        "protected finish artifact",
        "Do not push, merge, deploy",
        "human-review",
    )
    for fragment in prompt_requirements:
        if fragment not in prompt:
            errors.append(f"prompt is missing required safety rule: {fragment}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", type=Path, default=Path("WORKFLOW.md"))
    parser.add_argument("--json", action="store_true", help="emit a machine-readable result")
    args = parser.parse_args()
    path = args.workflow.expanduser().resolve()
    errors = validate(path)
    result = {
        "ok": not errors,
        "workflow": str(path),
        "errors": errors,
        "checks": [
            "github opt-in label",
            "isolated workspace",
            "Codex app-server",
            "approval and sandbox policy",
            "PDflow heavy-job boundary",
            "finish/candidate safety",
        ],
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif errors:
        print(f"Symphony workflow INVALID: {path}", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    else:
        print(f"Symphony workflow valid: {path}")
        print("- GitHub label gate: symphony")
        print("- workspace isolation: enabled")
        print("- Codex app-server: workspace-write / approval required")
        print("- PDflow heavy EDA: delegated to run_resource_job.sh")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

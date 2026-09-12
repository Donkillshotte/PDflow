"""Allowlisted PDflow action registry.

The action registry is deliberately separate from the executable registry:
tools describe host binaries, while actions describe repository-owned
workflows that are safe to request from the desktop UI.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LAB_VARIANT_RE = re.compile(r"^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$")


def is_lab_variant(variant: str) -> bool:
    """Return whether *variant* is a safe, repository-scoped ASAP7 name."""

    return bool(LAB_VARIANT_RE.fullmatch(variant))


@dataclass(frozen=True)
class ActionDescriptor:
    action_id: str
    display_name: str
    surface: str
    command: tuple[str, ...]
    timeout_seconds: int
    required_tools: tuple[str, ...]
    mutates: bool
    pythonpath: bool
    environment: dict[str, str]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ActionDescriptor":
        command = tuple(str(item) for item in raw.get("command", []))
        if not command:
            raise ValueError("action command cannot be empty")
        return cls(
            action_id=str(raw["action_id"]),
            display_name=str(raw.get("display_name") or raw["action_id"]),
            surface=str(raw.get("surface") or "generated"),
            command=command,
            timeout_seconds=int(raw.get("timeout_seconds") or 600),
            required_tools=tuple(str(item) for item in raw.get("required_tools", [])),
            mutates=bool(raw.get("mutates", False)),
            pythonpath=bool(raw.get("pythonpath", False)),
            environment={
                str(key): str(value)
                for key, value in (raw.get("environment") or {}).items()
            },
        )


def registry_path(repo_root: Path) -> Path:
    return repo_root / "config" / "pdflow" / "action_registry.json"


def load_actions(repo_root: Path) -> tuple[int, list[ActionDescriptor]]:
    raw = json.loads(registry_path(repo_root).read_text(encoding="utf-8"))
    return int(raw.get("default_timeout_seconds") or 600), [
        ActionDescriptor.from_dict(item) for item in raw.get("actions", [])
    ]


def get_action(repo_root: Path, action_id: str) -> ActionDescriptor:
    _, actions = load_actions(repo_root)
    for action in actions:
        if action.action_id == action_id:
            return action
    raise KeyError(f"unknown action: {action_id}")


def _repo_token(token: str, repo_root: Path) -> str:
    if not token.startswith("{repo}"):
        return token
    path = (repo_root / token[len("{repo}") :].lstrip("/")).resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("action path outside repository root") from exc
    return str(path)


def build_action_command(
    action: ActionDescriptor,
    repo_root: Path,
    *,
    variant: str,
    extra_args: list[str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    if variant not in {"flowlab", "learn", "eco_scratch"} and not is_lab_variant(variant):
        raise ValueError("invalid action variant")
    rendered: list[str] = []
    for token in action.command:
        value = _repo_token(token, repo_root)
        value = value.replace("{variant}", variant)
        rendered.append(value)
    if extra_args:
        raise ValueError("action arguments are not accepted by this registry entry")
    executable = shutil.which(rendered[0]) if not os.path.isabs(rendered[0]) else rendered[0]
    if not executable or not Path(executable).is_file() or not os.access(executable, os.X_OK):
        raise FileNotFoundError(f"action interpreter is unavailable: {rendered[0]}")
    rendered[0] = executable
    script = Path(rendered[1]) if len(rendered) > 1 else None
    if script is not None:
        try:
            script.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError("action script outside repository root") from exc
        if not script.is_file():
            raise FileNotFoundError(f"action script is missing: {script}")
    env: dict[str, str] = {"FLOW_VARIANT": variant}
    env.update(action.environment)
    if action.pythonpath:
        current = os.environ.get("PYTHONPATH")
        values = [str(repo_root / "learn"), "/usr/lib/python3/dist-packages"]
        if current:
            values.append(current)
        env["PYTHONPATH"] = os.pathsep.join(values)
    return rendered, env


def discover_actions(repo_root: Path, tool_registry: dict[str, Any]) -> list[dict[str, Any]]:
    # Callers include the CLI and lightweight tests, some of which provide a
    # relative checkout path.  Path safety below is defined against the
    # canonical project root, never against the caller's current directory.
    repo_root = repo_root.resolve()
    default_timeout, actions = load_actions(repo_root)
    by_tool = {
        item.get("tool_id"): item
        for item in tool_registry.get("tools", [])
        if isinstance(item, dict)
    }
    result: list[dict[str, Any]] = []
    for action in actions:
        interpreter = action.command[0]
        interpreter_ready = bool(shutil.which(interpreter))
        script_ready = True
        if len(action.command) > 1 and action.command[1].startswith("{repo}"):
            script_ready = _repo_token(action.command[1], repo_root) and Path(
                _repo_token(action.command[1], repo_root)
            ).is_file()
        missing_tools = [
            tool_id
            for tool_id in action.required_tools
            if by_tool.get(tool_id, {}).get("availability") != "READY"
        ]
        if not interpreter_ready or not script_ready:
            availability = "MISSING"
        elif missing_tools:
            availability = "GAP"
        else:
            availability = "READY"
        result.append(
            {
                "action_id": action.action_id,
                "display_name": action.display_name,
                "surface": action.surface,
                "timeout_seconds": action.timeout_seconds or default_timeout,
                "required_tools": list(action.required_tools),
                "mutates": action.mutates,
                "availability": availability,
                "missing_tools": missing_tools,
            }
        )
    return result

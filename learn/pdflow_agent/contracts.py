"""Shared local-agent contracts.

These dictionaries are deliberately boring and JSON-friendly. The Studio
client consumes the same shape, while the agent remains usable from shell
scripts and tests without importing frontend code.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
REPORT_STATUSES = ("PASS", "FAIL", "WARN", "PARTIAL", "PROXY", "GAP", "NOT_RUN")
EXECUTION_STATUSES = ("QUEUED", "RUNNING", "COMPLETED", "CANCELLED", "FAILED", "NOT_RUN")
TERMINATION_CAUSES = (
    "cancelled",
    "timeout",
    "memory",
    "resource_isolation",
    "refused",
    "crash",
)
JOB_STATES = (
    "QUEUED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "GAP",
    "DIRTY",
    "ORPHANED",
)
AUTHORITIES = ("finish", "candidate", "generated", "source")
SCOPES = ("product", "flow", "package", "lab", "generated")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str | None:
    """Return a streaming SHA-256 without loading a GDS/ODB in memory."""

    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                block = handle.read(chunk_size)
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def hash_text(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    """Write a JSON document atomically in the destination directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def validate_artifact(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["artifact must be an object"]
    required = {
        "artifact_id",
        "kind",
        "scope",
        "variant",
        "relative_path",
        "content_hash",
        "size",
        "mtime_ns",
        "revision",
        "producer",
        "run_id",
        "authority",
        "mutable",
    }
    errors = [f"missing {key}" for key in sorted(required - value.keys())]
    if value.get("scope") not in SCOPES:
        errors.append("invalid artifact scope")
    if value.get("authority") not in AUTHORITIES:
        errors.append("invalid artifact authority")
    for key in ("size", "mtime_ns", "revision"):
        if not isinstance(value.get(key), int) or value.get(key, -1) < 0:
            errors.append(f"invalid artifact {key}")
    if value.get("authority") == "finish" and value.get("mutable") is not False:
        errors.append("finish artifacts must be immutable")
    if value.get("authority") == "candidate" and value.get("mutable") is not True:
        errors.append("candidate artifacts must be mutable")
    relative = value.get("relative_path")
    if (
        not isinstance(relative, str)
        or not relative
        or relative.startswith("/")
        or "\x00" in relative
        or ".." in Path(relative).parts
    ):
        errors.append("invalid relative_path")
    return errors


def validate_report(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["report must be an object"]
    errors = []
    if value.get("status") not in REPORT_STATUSES:
        errors.append("invalid report status")
    if not isinstance(value.get("ok"), bool):
        errors.append("report ok must be boolean")
    if value.get("status") in {"GAP", "PARTIAL", "PROXY", "NOT_RUN"} and value.get("ok"):
        errors.append("non-signoff status cannot be ok")
    if value.get("status") == "PASS" and value.get("ok") is not True:
        errors.append("PASS report must have ok=true")
    if value.get("termination_cause") not in (None, *TERMINATION_CAUSES):
        errors.append("invalid termination_cause")
    for key in ("evidence_status", "requirement_status", "signoff_status"):
        if value.get(key) is not None and value.get(key) not in REPORT_STATUSES:
            errors.append(f"invalid {key}")
    if "product_signoff" in value and not isinstance(value.get("product_signoff"), bool):
        errors.append("product_signoff must be boolean")
    if value.get("product_signoff") is True and not (
        value.get("status") == "PASS"
        and value.get("ok") is True
        and value.get("signoff_status") == "PASS"
    ):
        errors.append("product_signoff requires a PASS report and signoff_status=PASS")
    if value.get("execution_status") is not None and value.get("execution_status") not in EXECUTION_STATUSES:
        errors.append("invalid execution_status")
    if value.get("comparison_scope") not in {
        "same-live-invocation",
        "not-comparable",
        "none",
    }:
        errors.append("invalid comparison_scope")
    for key in ("input_artifacts", "output_artifacts"):
        if not isinstance(value.get(key), list):
            errors.append(f"{key} must be an array")
    return errors


def validate_run(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["run must be an object"]
    errors = []
    if not isinstance(value.get("run_id"), str) or not _safe_run_id(
        value.get("run_id", "")
    ):
        errors.append("invalid run_id")
    if value.get("surface") not in {"product", "flow", "package", "lab", "tools"}:
        errors.append("invalid run surface")
    if not isinstance(value.get("input_artifacts"), list):
        errors.append("input_artifacts must be an array")
    return errors


def validate_tool_descriptor(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["tool descriptor must be an object"]
    required = {
        "tool_id",
        "display_name",
        "capabilities",
        "input_kinds",
        "output_kinds",
        "required",
        "timeout_seconds",
        "availability",
    }
    errors = [f"missing {key}" for key in sorted(required - value.keys())]
    if value.get("availability") not in {"READY", "MISSING", "MISCONFIGURED", "INCOMPATIBLE"}:
        errors.append("invalid tool availability")
    if not isinstance(value.get("timeout_seconds"), int) or value.get("timeout_seconds", 0) < 1:
        errors.append("invalid tool timeout_seconds")
    for key in ("capabilities", "input_kinds", "output_kinds"):
        if not isinstance(value.get(key), list):
            errors.append(f"{key} must be an array")
    if not isinstance(value.get("required"), bool):
        errors.append("required must be boolean")
    return errors


def validate_action_descriptor(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["action descriptor must be an object"]
    required = {
        "action_id",
        "display_name",
        "surface",
        "timeout_seconds",
        "required_tools",
        "mutates",
        "availability",
        "missing_tools",
    }
    errors = [f"missing {key}" for key in sorted(required - value.keys())]
    if value.get("surface") not in {"product", "flow", "package", "lab", "tools", "generated"}:
        errors.append("invalid action surface")
    if value.get("availability") not in {"READY", "MISSING", "GAP"}:
        errors.append("invalid action availability")
    if not isinstance(value.get("timeout_seconds"), int) or value.get("timeout_seconds", 0) < 1:
        errors.append("invalid action timeout_seconds")
    if not isinstance(value.get("required_tools"), list):
        errors.append("required_tools must be an array")
    if not isinstance(value.get("missing_tools"), list):
        errors.append("missing_tools must be an array")
    if not isinstance(value.get("mutates"), bool):
        errors.append("mutates must be boolean")
    return errors


def _safe_run_id(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"[A-Za-z0-9_.-]{8,100}", value))


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    kind: str
    scope: str
    variant: str
    relative_path: str
    content_hash: str | None
    size: int
    mtime_ns: int
    revision: int
    producer: str
    run_id: str | None
    authority: str
    mutable: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunContext:
    run_id: str
    surface: str
    design_id: str
    pdk_id: str
    profile: str
    created_at: str
    input_artifacts: list[str] = field(default_factory=list)
    tool_versions: dict[str, str | None] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    status: str = "RUNNING"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportEnvelope:
    report_id: str
    run_id: str | None
    scope: str
    status: str
    ok: bool
    execution_status: str = "COMPLETED"
    evidence_status: str = "NOT_RUN"
    requirement_status: str = "NOT_RUN"
    signoff_status: str = "NOT_RUN"
    product_signoff: bool = False
    input_artifacts: list[str] = field(default_factory=list)
    input_artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    output_artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    required_checks: list[dict[str, Any]] = field(default_factory=list)
    checkpoint_id: str | None = None
    configuration_hash: str | None = None
    units: dict[str, str] = field(default_factory=dict)
    corner: str | None = None
    mode: str | None = None
    activity_source: str | None = None
    limitations: list[str] = field(default_factory=list)
    mesh_id: str | None = None
    oracle: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    relative: list[dict[str, Any]] = field(default_factory=list)
    comparison_scope: str = "none"
    report_paths: list[str] = field(default_factory=list)
    reason: str | None = None
    tool_versions: dict[str, str | None] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    job_id: str | None = None
    operation: str | None = None
    resource: dict[str, Any] = field(default_factory=dict)
    termination_cause: str | None = None
    stale: bool = False
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def gap(
        cls,
        *,
        report_id: str,
        reason: str,
        run_id: str | None = None,
        scope: str = "generated",
    ) -> "ReportEnvelope":
        return cls(
            report_id=report_id,
            run_id=run_id,
            scope=scope,
            status="GAP",
            ok=False,
            execution_status="NOT_RUN",
            evidence_status="GAP",
            requirement_status="GAP",
            signoff_status="GAP",
            reason=reason,
            comparison_scope="none",
        )


def finish_authority(relative_path: str) -> tuple[str, bool]:
    """Classify canonical result artifacts without trusting filename-only reports.

    Every ORFS checkpoint under the protected results tree is a canonical
    input from the agent's point of view, not only ``6_final.*``.  Treating an
    intermediate ODB as mutable allowed an edit launch to write directly into
    the live FlowLab tree, which is exactly the class of destructive mistake
    the candidate boundary is meant to prevent.
    """

    normalized = relative_path.replace("\\", "/")
    if (
        (normalized.startswith(".pdflow/runs/") or "/.pdflow/runs/" in normalized)
        and "/candidate/" in normalized
    ):
        return "candidate", True
    if normalized.startswith("tools/OpenROAD-flow-scripts/flow/results/"):
        # eco_scratch is intentionally isolated from the canonical FlowLab
        # finish, but it is still editable scratch rather than a product
        # finish. All other ORFS variants are read-only canonical inputs.
        if "/eco_scratch/" in normalized:
            return "candidate", True
        return "finish", False
    if "/sim/reports/" in normalized or "/sim/previews/" in normalized:
        return "generated", True
    if normalized.startswith(".pdflow/generated/"):
        return "generated", True
    return "source", True

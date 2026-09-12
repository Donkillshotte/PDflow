"""Declarative tool registry and host discovery."""

from __future__ import annotations

import json
import os
import copy
import signal
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Registry discovery is called by several UI/API paths.  Version probes are
# real native processes, so concurrent requests must not fan out into one
# probe per browser poll.  The cache is deliberately short-lived: installing
# or repairing a tool becomes visible without requiring an agent restart while
# a burst of identical requests is collapsed into one discovery pass.
_DISCOVERY_CACHE_TTL_SECONDS = 10.0
_DISCOVERY_CACHE_LOCK = threading.Lock()
_DISCOVERY_SINGLE_FLIGHT = threading.Lock()
_DISCOVERY_CACHE: dict[
    Path, tuple[int, tuple[tuple[str, str], ...], float, dict[str, Any]]
] = {}


@dataclass(frozen=True)
class ToolDescriptor:
    tool_id: str
    display_name: str
    required: bool
    description: str
    capabilities: tuple[str, ...]
    executable_env: tuple[str, ...]
    executable_candidates: tuple[str, ...]
    commands: dict[str, list[str]]
    version_probe: tuple[str, ...]
    version_probe_exit_codes: tuple[int, ...]
    version_label: str | None
    launch_profiles: tuple[str, ...]
    report_parsers: tuple[str, ...]
    status_mapping: dict[str, str]
    input_kinds: tuple[str, ...]
    output_kinds: tuple[str, ...]
    timeout_seconds: int
    required_dependencies: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ToolDescriptor":
        return cls(
            tool_id=str(raw["tool_id"]),
            display_name=str(raw.get("display_name") or raw["tool_id"]),
            required=bool(raw.get("required", True)),
            description=str(raw.get("description") or ""),
            capabilities=tuple(str(x) for x in raw.get("capabilities", [])),
            executable_env=tuple(str(x) for x in raw.get("executable_env", [])),
            executable_candidates=tuple(
                str(x) for x in raw.get("executable_candidates", [])
            ),
            commands={
                str(key): [str(part) for part in value]
                for key, value in (raw.get("commands") or {}).items()
            },
            version_probe=tuple(str(x) for x in raw.get("version_probe", ["--version"])),
            version_probe_exit_codes=tuple(
                int(x) for x in raw.get("version_probe_exit_codes", [0])
            ),
            version_label=(
                str(raw["version_label"])
                if raw.get("version_label") is not None
                else None
            ),
            launch_profiles=tuple(str(x) for x in raw.get("launch_profiles", [])),
            report_parsers=tuple(str(x) for x in raw.get("report_parsers", [])),
            status_mapping={
                str(key): str(value)
                for key, value in (raw.get("status_mapping") or {}).items()
            },
            input_kinds=tuple(str(x) for x in raw.get("input_kinds", [])),
            output_kinds=tuple(str(x) for x in raw.get("output_kinds", [])),
            timeout_seconds=int(raw.get("timeout_seconds") or 600),
            required_dependencies=tuple(
                str(x) for x in raw.get("required_dependencies", [])
            ),
        )


def registry_path(repo_root: Path) -> Path:
    return repo_root / "config" / "pdflow" / "tool_registry.json"


def load_registry(repo_root: Path) -> tuple[int, list[ToolDescriptor]]:
    path = registry_path(repo_root)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return int(raw.get("default_timeout_seconds") or 600), [
        ToolDescriptor.from_dict(item) for item in raw.get("tools", [])
    ]


def _resolve_candidate(candidate: str, repo_root: Path) -> str | None:
    expanded = os.path.expanduser(candidate)
    if expanded.startswith("{repo}"):
        expanded = str(repo_root) + expanded[len("{repo}") :]
    path = Path(expanded)
    if path.is_absolute():
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(expanded)


def resolve_executable(tool: ToolDescriptor, repo_root: Path) -> str | None:
    for env_name in tool.executable_env:
        value = os.environ.get(env_name)
        if value:
            resolved = _resolve_candidate(value, repo_root)
            if resolved:
                return resolved
    for candidate in tool.executable_candidates:
        resolved = _resolve_candidate(candidate, repo_root)
        if resolved:
            return resolved
    return None


def _probe_version(
    executable: str,
    probe: tuple[str, ...],
    accepted_exit_codes: tuple[int, ...] = (0,),
) -> str | None:
    # Version probes are kept side-effect free. A non-zero probe is a
    # misconfiguration even when the binary happens to print a banner.  They
    # still get their own process group so a native launcher that forks cannot
    # survive a timeout and become an untracked agent child.
    process: subprocess.Popen[str] | None = None
    try:
        probe_env = os.environ.copy()
        # Discovery must not reserve the numerical thread budget used by a
        # real job.  These values affect only the short-lived version probe.
        for name in (
            "BLIS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "RAYON_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        ):
            probe_env[name] = "1"
        # KLayout and other Qt-linked tools should never try to create a
        # native window merely to report their version.
        probe_env.setdefault("QT_QPA_PLATFORM", "offscreen")
        process = subprocess.Popen(
            [executable, *probe],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
            start_new_session=True,
            env=probe_env,
        )
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                process.communicate(timeout=1)
            except (OSError, subprocess.SubprocessError):
                pass
        return None
    except (OSError, subprocess.SubprocessError):
        return None
    output = (stdout or stderr or "").strip()
    if process.returncode not in accepted_exit_codes:
        return None
    if not output:
        return None
    # Some native tools (notably ngspice) print a decorative banner before
    # the actual version.  Expose a stable, useful line to the UI while still
    # treating the probe as a strict executable check.
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    meaningful = [
        line
        for line in lines
        if set(line) - {"*", "-", "=", " "}
    ]
    return (meaningful[0] if meaningful else lines[0])[:240]


def _discover_uncached(
    repo_root: Path,
    default_timeout: int,
    tools: list[ToolDescriptor],
) -> dict[str, Any]:
    discovered: list[dict[str, Any]] = []
    versions: dict[str, str | None] = {}
    for tool in tools:
        executable = resolve_executable(tool, repo_root)
        probe_output = (
            _probe_version(
                executable,
                tool.version_probe,
                tool.version_probe_exit_codes,
            )
            if executable
            else None
        )
        version = tool.version_label or probe_output
        status = (
            "MISSING"
            if not executable
            else "READY"
            if version is not None
            else "MISCONFIGURED"
        )
        versions[tool.tool_id] = version
        discovered.append(
            {
                "tool_id": tool.tool_id,
                "display_name": tool.display_name,
                "required": tool.required,
                "description": tool.description,
                "capabilities": list(tool.capabilities),
                "input_kinds": list(tool.input_kinds),
                "output_kinds": list(tool.output_kinds),
                "timeout_seconds": tool.timeout_seconds or default_timeout,
                "required_dependencies": list(tool.required_dependencies),
                "version_probe": list(tool.version_probe),
                "version_probe_exit_codes": list(tool.version_probe_exit_codes),
                "version_label": tool.version_label,
                "launch_profiles": list(tool.launch_profiles),
                "report_parsers": list(tool.report_parsers),
                "status_mapping": dict(tool.status_mapping),
                "availability": status,
                "executable": executable,
                "version": version,
            }
        )
    return {
        "schema_version": 1,
        "default_timeout_seconds": default_timeout,
        "platform": "linux",
        "tools": discovered,
        "tool_versions": versions,
    }


def discover(repo_root: Path, *, force: bool = False) -> dict[str, Any]:
    default_timeout, tools = load_registry(repo_root)
    path = registry_path(repo_root)
    try:
        registry_mtime_ns = path.stat().st_mtime_ns
    except OSError:
        registry_mtime_ns = 0
    env_names = {"PATH"}
    for tool in tools:
        env_names.update(tool.executable_env)
    env_signature = tuple(sorted((name, os.environ.get(name, "")) for name in env_names))
    cache_key = repo_root.resolve()
    now = time.monotonic()

    # Hold the lock through discovery (the probes are bounded to five seconds
    # each) to provide single-flight semantics.  This is preferable to
    # spawning duplicate native processes while another request is probing.
    with _DISCOVERY_CACHE_LOCK:
        cached = _DISCOVERY_CACHE.get(cache_key)
        if (
            not force
            and cached is not None
            and cached[0] == registry_mtime_ns
            and cached[1] == env_signature
            and now - cached[2] < _DISCOVERY_CACHE_TTL_SECONDS
        ):
            return copy.deepcopy(cached[3])

    # A second check after acquiring the single-flight lock prevents a
    # waiting request from repeating the probes completed by its predecessor.
    with _DISCOVERY_SINGLE_FLIGHT:
        with _DISCOVERY_CACHE_LOCK:
            cached = _DISCOVERY_CACHE.get(cache_key)
            if (
                not force
                and cached is not None
                and cached[0] == registry_mtime_ns
                and cached[1] == env_signature
                and time.monotonic() - cached[2] < _DISCOVERY_CACHE_TTL_SECONDS
            ):
                return copy.deepcopy(cached[3])
        result = _discover_uncached(repo_root, default_timeout, tools)
        with _DISCOVERY_CACHE_LOCK:
            _DISCOVERY_CACHE[cache_key] = (
                registry_mtime_ns,
                env_signature,
                time.monotonic(),
                copy.deepcopy(result),
            )
        return result


def get_tool(repo_root: Path, tool_id: str) -> tuple[ToolDescriptor, str | None]:
    _, tools = load_registry(repo_root)
    for tool in tools:
        if tool.tool_id == tool_id:
            return tool, resolve_executable(tool, repo_root)
    raise KeyError(f"unknown tool: {tool_id}")


def build_command(
    *,
    tool: ToolDescriptor,
    executable: str,
    operation: str,
    artifact: Path | None,
    script: Path | None = None,
    args: list[str] | None = None,
    web_port: int | None = None,
) -> list[str]:
    template = tool.commands.get(operation)
    if not template:
        raise ValueError(f"tool {tool.tool_id} has no operation {operation}")
    values = {
        "{executable}": executable,
        "{artifact}": str(artifact) if artifact else "",
        "{script}": str(script) if script else "",
        "{web_port}": str(web_port or ""),
        "{args}": "",
    }
    rendered: list[str] = []
    for part in template:
        if part == "{args}":
            rendered.extend(args or [])
            continue
        rendered.append(values.get(part, part))
    return [item for item in rendered if item]

"""Bounded, host-local execution for PDflow heavy work.

The runner deliberately has one backend: a transient systemd user service on
Linux with cgroup v2 resource controls.  There is no unisolated fallback.
This keeps a tool crash or a memory spike inside a cgroup that is separate
from the desktop application and makes the termination cause observable.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import re
import selectors
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


class ResourceRunnerError(RuntimeError):
    """Base error raised before a heavy process is allowed to start."""


class ResourceIsolationUnavailable(ResourceRunnerError):
    """The host cannot provide the required systemd/cgroup isolation."""


class ResourceConfigurationError(ResourceRunnerError):
    """An unsafe or inconsistent resource override was requested."""


_UNIT_RE = re.compile(r"^[A-Za-z0-9_.@:-]{1,180}$")
_SENSITIVE_ENV_RE = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY)$",
    re.IGNORECASE,
)

DEFAULT_MEMORY_MAX_BYTES = 6 * 1024**3
DEFAULT_MEMORY_HIGH_BYTES = 5 * 1024**3
DEFAULT_MEMORY_SWAP_MAX_BYTES = 512 * 1024**2
DEFAULT_CPU_QUOTA_PERCENT = 400
DEFAULT_MIN_AVAILABLE_BYTES = 4 * 1024**3
DEFAULT_LOG_MAX_BYTES = 64 * 1024**2
DEFAULT_LOG_TAIL_BYTES = 16 * 1024
DEFAULT_MAX_FULL_PRESSURE_AVG10 = 10.0
DEFAULT_QUEUE_POLL_SECONDS = 0.25
DEFAULT_PREFLIGHT_TIMEOUT_SECONDS = 10
DEFAULT_TIMEOUT_SECONDS = 600


def _parse_number(value: str | None, *, name: str, integer: bool = True) -> int:
    if value is None or not value.strip():
        raise ResourceConfigurationError(f"{name} must be a positive number")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ResourceConfigurationError(f"{name} must be numeric") from exc
    if not parsed > 0 or (integer and not parsed.is_integer()):
        raise ResourceConfigurationError(f"{name} must be positive")
    return int(parsed) if integer else int(parsed)


def _parse_float(value: str | None, *, name: str, default: float) -> float:
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ResourceConfigurationError(f"{name} must be numeric") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise ResourceConfigurationError(f"{name} must be a finite non-negative number")
    return parsed


def _parse_size(value: str | None, *, name: str, default: int) -> int:
    if value is None or not value.strip():
        return default
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgt]?i?b)?\s*", value, re.I)
    if not match:
        raise ResourceConfigurationError(
            f"{name} must be a positive byte value (for example 6GiB)"
        )
    amount = float(match.group(1))
    suffix = (match.group(2) or "b").lower()
    factors = {
        "b": 1,
        "kb": 1000,
        "kib": 1024,
        "mb": 1000**2,
        "mib": 1024**2,
        "gb": 1000**3,
        "gib": 1024**3,
        "tb": 1000**4,
        "tib": 1024**4,
    }
    parsed = int(amount * factors[suffix])
    if parsed <= 0:
        raise ResourceConfigurationError(f"{name} must be positive")
    return parsed


def _read_meminfo_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1]) * 1024
    except (OSError, ValueError):
        return None
    return None


def _read_psi_memory() -> dict[str, float | None]:
    values: dict[str, float | None] = {"some_avg10": None, "full_avg10": None}
    try:
        lines = Path("/proc/pressure/memory").read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        fields = dict(
            item.split("=", 1)
            for item in line.split()[1:]
            if "=" in item
        )
        key = "some_avg10" if line.startswith("some ") else "full_avg10"
        try:
            values[key] = float(fields.get("avg10"))
        except (TypeError, ValueError):
            pass
    return values


def _read_cgroup_file(cgroup_path: str, name: str) -> str | None:
    relative = cgroup_path.lstrip("/")
    if not relative or ".." in Path(relative).parts:
        return None
    path = Path("/sys/fs/cgroup") / relative / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _parse_key_values(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    result: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def _parse_systemd_size(value: str | None) -> int | None:
    if not value or value in {"infinity", "[not set]"}:
        return None
    try:
        return _parse_size(value, name="systemd memory value", default=0)
    except ResourceConfigurationError:
        return None


def _merge_resource_samples(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    """Retain cgroup counters when systemd unloads a transient unit.

    A short-lived user service can disappear between two ``systemctl show``
    calls.  In that window systemd reports the terminal state but no memory
    or CPU accounting fields, while the previous sample still contains the
    useful peak/counter values.  Keep the newest lifecycle state and merge
    only monotonic resource observations so the final report remains
    diagnosable without inventing measurements.
    """
    if not previous:
        return current

    merged = dict(current)
    if not merged.get("cgroup"):
        merged["cgroup"] = previous.get("cgroup")

    previous_events = previous.get("memory_events") or {}
    current_events = merged.get("memory_events") or {}
    if previous_events or current_events:
        merged["memory_events"] = {
            key: max(int(previous_events.get(key, 0)), int(value))
            for key, value in {**previous_events, **current_events}.items()
        }

    merged["resource_exhausted"] = bool(
        merged.get("resource_exhausted") or previous.get("resource_exhausted")
    )
    if not merged.get("resource_cause"):
        merged["resource_cause"] = previous.get("resource_cause")

    previous_systemd = previous.get("systemd") or {}
    current_systemd = dict(merged.get("systemd") or {})
    for key in (
        "memory_peak_bytes",
        "memory_current",
        "memory_swap_current",
        "cpu_usage_ns",
    ):
        previous_value = previous_systemd.get(key)
        current_value = current_systemd.get(key)
        if current_value is None and previous_value is not None:
            current_systemd[key] = previous_value
        elif key == "memory_peak_bytes" and previous_value is not None:
            current_systemd[key] = max(int(current_value or 0), int(previous_value))
    merged["systemd"] = current_systemd
    return merged


@dataclass(frozen=True)
class ResourceLimits:
    memory_max_bytes: int = DEFAULT_MEMORY_MAX_BYTES
    memory_high_bytes: int = DEFAULT_MEMORY_HIGH_BYTES
    memory_swap_max_bytes: int = DEFAULT_MEMORY_SWAP_MAX_BYTES
    cpu_quota_percent: int = DEFAULT_CPU_QUOTA_PERCENT
    min_available_bytes: int = DEFAULT_MIN_AVAILABLE_BYTES
    log_max_bytes: int = DEFAULT_LOG_MAX_BYTES
    log_tail_bytes: int = DEFAULT_LOG_TAIL_BYTES
    max_full_pressure_avg10: float = DEFAULT_MAX_FULL_PRESSURE_AVG10

    @classmethod
    def from_environment(cls) -> "ResourceLimits":
        memory_max = _parse_size(
            os.environ.get("PD_FLOW_RESOURCE_MEMORY_MAX"),
            name="PD_FLOW_RESOURCE_MEMORY_MAX",
            default=DEFAULT_MEMORY_MAX_BYTES,
        )
        memory_high = _parse_size(
            os.environ.get("PD_FLOW_RESOURCE_MEMORY_HIGH"),
            name="PD_FLOW_RESOURCE_MEMORY_HIGH",
            default=DEFAULT_MEMORY_HIGH_BYTES,
        )
        swap_max = _parse_size(
            os.environ.get("PD_FLOW_RESOURCE_SWAP_MAX"),
            name="PD_FLOW_RESOURCE_SWAP_MAX",
            default=DEFAULT_MEMORY_SWAP_MAX_BYTES,
        )
        cpu = _parse_number(
            os.environ.get("PD_FLOW_RESOURCE_CPU_QUOTA_PERCENT"),
            name="PD_FLOW_RESOURCE_CPU_QUOTA_PERCENT",
        ) if os.environ.get("PD_FLOW_RESOURCE_CPU_QUOTA_PERCENT") else DEFAULT_CPU_QUOTA_PERCENT
        min_available = _parse_size(
            os.environ.get("PD_FLOW_RESOURCE_MIN_AVAILABLE"),
            name="PD_FLOW_RESOURCE_MIN_AVAILABLE",
            default=DEFAULT_MIN_AVAILABLE_BYTES,
        )
        log_max = _parse_size(
            os.environ.get("PD_FLOW_RESOURCE_LOG_MAX"),
            name="PD_FLOW_RESOURCE_LOG_MAX",
            default=DEFAULT_LOG_MAX_BYTES,
        )
        log_tail = _parse_size(
            os.environ.get("PD_FLOW_RESOURCE_LOG_TAIL"),
            name="PD_FLOW_RESOURCE_LOG_TAIL",
            default=DEFAULT_LOG_TAIL_BYTES,
        )
        max_full_pressure = _parse_float(
            os.environ.get("PD_FLOW_RESOURCE_MAX_FULL_PRESSURE_AVG10"),
            name="PD_FLOW_RESOURCE_MAX_FULL_PRESSURE_AVG10",
            default=DEFAULT_MAX_FULL_PRESSURE_AVG10,
        )
        limits = cls(
            memory_max_bytes=memory_max,
            memory_high_bytes=memory_high,
            memory_swap_max_bytes=swap_max,
            cpu_quota_percent=cpu,
            min_available_bytes=min_available,
            log_max_bytes=log_max,
            log_tail_bytes=log_tail,
            max_full_pressure_avg10=max_full_pressure,
        )
        limits.validate()
        return limits

    def validate(self) -> None:
        if self.memory_high_bytes > self.memory_max_bytes:
            raise ResourceConfigurationError("memory high threshold exceeds memory max")
        if self.min_available_bytes < 4 * 1024**3 and os.environ.get(
            "PD_FLOW_RESOURCE_ALLOW_UNSAFE_OVERRIDE"
        ) != "1":
            raise ResourceConfigurationError(
                "min host availability cannot be lowered below 4GiB without "
                "PD_FLOW_RESOURCE_ALLOW_UNSAFE_OVERRIDE=1"
            )
        increases = (
            self.memory_max_bytes > DEFAULT_MEMORY_MAX_BYTES
            or self.memory_high_bytes > DEFAULT_MEMORY_HIGH_BYTES
            or self.memory_swap_max_bytes > DEFAULT_MEMORY_SWAP_MAX_BYTES
            or self.cpu_quota_percent > DEFAULT_CPU_QUOTA_PERCENT
        )
        if increases and os.environ.get("PD_FLOW_RESOURCE_ALLOW_INCREASE") != "1":
            raise ResourceConfigurationError(
                "resource limits above the safe defaults require "
                "PD_FLOW_RESOURCE_ALLOW_INCREASE=1"
            )
        if self.cpu_quota_percent > max(1, (os.cpu_count() or 1) * 100):
            raise ResourceConfigurationError("CPU quota exceeds the host CPU count")
        if not math.isfinite(self.max_full_pressure_avg10) or not 0 <= self.max_full_pressure_avg10 <= 100:
            raise ResourceConfigurationError("memory pressure threshold must be between 0 and 100")
        if (
            self.max_full_pressure_avg10 > DEFAULT_MAX_FULL_PRESSURE_AVG10
            and os.environ.get("PD_FLOW_RESOURCE_ALLOW_INCREASE") != "1"
        ):
            raise ResourceConfigurationError(
                "memory pressure threshold above the safe default requires "
                "PD_FLOW_RESOURCE_ALLOW_INCREASE=1"
            )

    def to_dict(self, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, int | float | str]:
        return {
            "memory_max_bytes": self.memory_max_bytes,
            "memory_high_bytes": self.memory_high_bytes,
            "memory_swap_max_bytes": self.memory_swap_max_bytes,
            "cpu_quota_percent": self.cpu_quota_percent,
            "min_available_bytes": self.min_available_bytes,
            "log_max_bytes": self.log_max_bytes,
            "log_tail_bytes": self.log_tail_bytes,
            "max_full_pressure_avg10": self.max_full_pressure_avg10,
            "timeout_seconds": timeout_seconds,
        }


def _resource_lock_path(repo_root: Path | None = None) -> Path:
    override = os.environ.get("PD_FLOW_RESOURCE_LOCK_PATH")
    if override:
        path = Path(override).expanduser()
    else:
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        if not runtime:
            runtime_candidate = Path(f"/run/user/{os.getuid()}")
            runtime = str(runtime_candidate) if runtime_candidate.is_dir() else ""
        if not runtime:
            raise ResourceIsolationUnavailable(
                "XDG_RUNTIME_DIR is unavailable; cannot create a host-wide resource lock"
            )
        path = Path(runtime) / "pdflow" / "heavy-job.lock"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.parent.is_dir() or not os.access(path.parent, os.W_OK):
            raise OSError("lock directory is not writable")
    except OSError as exc:
        raise ResourceIsolationUnavailable(
            f"resource lock is unavailable at {path}: {exc}"
        ) from exc
    return path


def host_snapshot() -> dict[str, Any]:
    return {
        "mem_available_bytes": _read_meminfo_bytes(),
        "memory_pressure": _read_psi_memory(),
    }


class ResourceLease:
    def __init__(self, handle: Any, path: Path, waited_seconds: float) -> None:
        self._handle = handle
        self.path = path
        self.waited_seconds = waited_seconds
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._released = True

    def __enter__(self) -> "ResourceLease":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.release()


class BoundedLog:
    """Stream a complete log up to a declared cap while keeping a tiny tail."""

    def __init__(self, path: Path, *, max_bytes: int, tail_bytes: int) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.tail_bytes = tail_bytes
        self.bytes_written = 0
        self.bytes_seen = 0
        self.truncated = False
        self._tail = bytearray()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("wb")

    def append(self, data: bytes) -> None:
        if not data:
            return
        self.bytes_seen += len(data)
        self._tail.extend(data)
        if len(self._tail) > self.tail_bytes:
            del self._tail[: -self.tail_bytes]
        if self.bytes_written < self.max_bytes:
            allowed = min(len(data), self.max_bytes - self.bytes_written)
            self._file.write(data[:allowed])
            self.bytes_written += allowed
            if allowed < len(data):
                self.truncated = True
        else:
            self.truncated = True

    def tail_text(self) -> str:
        return bytes(self._tail).decode("utf-8", errors="replace")[-self.tail_bytes :]

    def close(self) -> None:
        if self.truncated and self.bytes_written < self.max_bytes:
            marker = (
                f"\n[PDflow log cap reached: {self.max_bytes} bytes; "
                f"observed at least {self.bytes_seen} bytes]\n"
            ).encode("utf-8")
            self._file.write(marker[: self.max_bytes - self.bytes_written])
            self.bytes_written = min(self.max_bytes, self.bytes_written + len(marker))
        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.close()

    def __enter__(self) -> "BoundedLog":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()


def _controlled_refusal_reason(log_tail: str) -> str | None:
    """Return a bounded repository safety refusal from a command log."""

    for line in reversed(log_tail.splitlines()):
        message = line.strip()
        if message.startswith(("REFUSED:", "PREVIEW_GAP")):
            return message[:2048]
    return None


class ManagedProcess:
    def __init__(
        self,
        *,
        popen: subprocess.Popen[bytes],
        executor: "ResourceExecutor",
        lease: ResourceLease,
        unit_name: str,
        started_at: float,
        initial_host: dict[str, Any],
        timeout_seconds: int,
    ) -> None:
        self.popen = popen
        self.executor = executor
        self.lease = lease
        self.unit_name = unit_name
        self.started_at = started_at
        self.initial_host = initial_host
        self.timeout_seconds = timeout_seconds
        self._cgroup_path: str | None = None
        self.termination_requested: str | None = None
        self._finished = False
        self._final_resource: dict[str, Any] | None = None
        self._last_resource: dict[str, Any] | None = None

    @property
    def pid(self) -> int:
        return self.popen.pid

    @property
    def stdout(self) -> Any:
        return self.popen.stdout

    def poll(self) -> int | None:
        return self.popen.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self.popen.wait(timeout=timeout)

    def terminate(self, reason: str) -> None:
        self.termination_requested = reason
        self.executor.stop_unit(self.unit_name)
        if self.popen.poll() is None:
            try:
                self.popen.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    self.popen.terminate()
                    self.popen.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        self.popen.kill()
                    except OSError:
                        pass

    def resource_metadata(self) -> dict[str, Any]:
        if self._final_resource is not None:
            return dict(self._final_resource)
        if self._cgroup_path is None:
            self._cgroup_path = self.executor.unit_cgroup(self.unit_name)
        metadata = self.executor.unit_metadata(
            self.unit_name,
            cgroup_path=self._cgroup_path,
            initial_host=self.initial_host,
            waited_seconds=self.lease.waited_seconds,
            timeout_seconds=self.timeout_seconds,
        )
        # The unit may not be resolvable by the dedicated ControlGroup probe
        # on its first millisecond, while the richer `systemctl show` call
        # already returned the path. Persist either source so later final
        # metadata cannot lose the cgroup identity for a short-lived job.
        if self._cgroup_path is None and metadata.get("cgroup"):
            self._cgroup_path = str(metadata["cgroup"])
        metadata = _merge_resource_samples(self._last_resource, metadata)
        self._last_resource = metadata
        return metadata

    @property
    def finished(self) -> bool:
        return self._finished

    def finish(self) -> dict[str, Any]:
        if self._finished:
            return dict(self._final_resource or {})
        try:
            previous_resource = self._last_resource
            self._final_resource = self.resource_metadata()
            if previous_resource:
                previous_events = previous_resource.get("memory_events") or {}
                current_events = self._final_resource.get("memory_events") or {}
                self._final_resource["memory_events"] = {
                    key: max(int(previous_events.get(key, 0)), int(value))
                    for key, value in {**previous_events, **current_events}.items()
                }
                self._final_resource["resource_exhausted"] = bool(
                    self._final_resource.get("resource_exhausted")
                    or previous_resource.get("resource_exhausted")
                )
                if not self._final_resource.get("resource_cause"):
                    self._final_resource["resource_cause"] = previous_resource.get("resource_cause")
                if not self._final_resource.get("cgroup"):
                    self._final_resource["cgroup"] = previous_resource.get("cgroup")
                previous_systemd = previous_resource.get("systemd") or {}
                current_systemd = self._final_resource.setdefault("systemd", {})
                for key in (
                    "memory_peak_bytes",
                    "memory_current",
                    "memory_swap_current",
                    "cpu_usage_ns",
                ):
                    previous_value = previous_systemd.get(key)
                    current_value = current_systemd.get(key)
                    if current_value is None and previous_value is not None:
                        current_systemd[key] = previous_value
                    elif key == "memory_peak_bytes" and previous_value is not None:
                        current_systemd[key] = max(int(current_value or 0), int(previous_value))
            self._final_resource["return_code"] = self.poll()
            self._final_resource["termination_requested"] = self.termination_requested
        finally:
            self.executor.cleanup_unit(self.unit_name)
            self.lease.release()
            self._finished = True
        return dict(self._final_resource or {})


class ResourceExecutor:
    """Single-slot systemd user-service executor shared by local processes."""

    def __init__(
        self,
        repo_root: Path | None = None,
        *,
        limits: ResourceLimits | None = None,
    ) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self.limits = limits or ResourceLimits.from_environment()
        self._preflight_lock = threading.Lock()
        self._preflight_result: dict[str, Any] | None = None

    def describe(self) -> dict[str, Any]:
        result = {
            "executor": "systemd-user-cgroup-v2",
            "queue": "single-heavy-slot",
            "limits": self.limits.to_dict(),
            "host": host_snapshot(),
        }
        try:
            preflight = self.preflight()
        except ResourceRunnerError as exc:
            preflight = {"available": False, "reason": str(exc)}
        result.update(preflight)
        return result

    def preflight(self, *, force: bool = False) -> dict[str, Any]:
        with self._preflight_lock:
            if self._preflight_result is not None and not force:
                return dict(self._preflight_result)
            if sys.platform != "linux":
                result = {"available": False, "reason": "Linux is required"}
                self._preflight_result = result
                return dict(result)
            cgroup = Path("/sys/fs/cgroup")
            try:
                controllers = (cgroup / "cgroup.controllers").read_text(encoding="utf-8").split()
            except OSError as exc:
                result = {"available": False, "reason": f"cgroup v2 unavailable: {exc}"}
                self._preflight_result = result
                return dict(result)
            required = {"cpu", "memory", "pids"}
            if not required <= set(controllers):
                result = {
                    "available": False,
                    "reason": "cgroup v2 lacks required controllers: "
                    + ", ".join(sorted(required - set(controllers))),
                }
                self._preflight_result = result
                return dict(result)
            systemd_run = shutil.which("systemd-run")
            systemctl = shutil.which("systemctl")
            if not systemd_run or not systemctl:
                result = {"available": False, "reason": "systemd-run/systemctl unavailable"}
                self._preflight_result = result
                return dict(result)
            try:
                lock_path = _resource_lock_path(self.repo_root)
            except ResourceRunnerError as exc:
                result = {"available": False, "reason": str(exc)}
                self._preflight_result = result
                return dict(result)
            unit = f"pdflow-preflight-{os.getpid()}-{uuid.uuid4().hex[:10]}"
            command = [
                systemd_run,
                "--user",
                "--quiet",
                "--wait",
                "--pipe",
                "--unit",
                unit,
                "--working-directory",
                str(self.repo_root),
                "-p",
                "MemoryMax=16M",
                "-p",
                "MemoryHigh=8M",
                "-p",
                "MemorySwapMax=0",
                "-p",
                "CPUQuota=100%",
                "-p",
                "KillMode=control-group",
                "--",
                "/bin/true",
            ]
            try:
                probe = subprocess.run(
                    command,
                    cwd=str(self.repo_root),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=DEFAULT_PREFLIGHT_TIMEOUT_SECONDS,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                result = {"available": False, "reason": f"systemd cgroup probe failed: {exc}"}
                self._preflight_result = result
                return dict(result)
            if probe.returncode != 0:
                detail = (probe.stderr or probe.stdout or "probe returned non-zero").strip()
                result = {"available": False, "reason": f"systemd cgroup probe failed: {detail}"}
                self._preflight_result = result
                return dict(result)
            result = {
                "available": True,
                "isolation": "systemd-user-cgroup-v2",
                "lock_path": str(lock_path),
                "controllers": sorted(required),
            }
            self._preflight_result = result
            return dict(result)

    def _ensure_available(self) -> None:
        result = self.preflight()
        if not result.get("available"):
            raise ResourceIsolationUnavailable(str(result.get("reason") or "resource isolation unavailable"))

    def acquire(
        self,
        *,
        cancel_event: threading.Event | None = None,
        on_wait: Callable[[dict[str, Any]], None] | None = None,
    ) -> ResourceLease | None:
        self._ensure_available()
        path = _resource_lock_path(self.repo_root)
        try:
            handle = path.open("a+")
        except OSError as exc:
            raise ResourceIsolationUnavailable(f"cannot open resource lock {path}: {exc}") from exc
        started = time.monotonic()
        last_report = 0.0
        initial_snapshot = host_snapshot()
        if initial_snapshot.get("mem_available_bytes") is None:
            handle.close()
            raise ResourceIsolationUnavailable(
                "host MemAvailable cannot be verified; refusing heavy job start"
            )
        if (initial_snapshot.get("memory_pressure") or {}).get("full_avg10") is None:
            handle.close()
            raise ResourceIsolationUnavailable(
                "host memory pressure cannot be verified; refusing heavy job start"
            )
        while True:
            if cancel_event is not None and cancel_event.is_set():
                handle.close()
                return None
            snapshot = host_snapshot()
            available = snapshot.get("mem_available_bytes")
            pressure = snapshot.get("memory_pressure") or {}
            full_pressure = pressure.get("full_avg10")
            memory_ready = available is not None and available >= self.limits.min_available_bytes
            pressure_ready = full_pressure is not None and full_pressure <= self.limits.max_full_pressure_avg10
            now = time.monotonic()
            if on_wait is not None and now - last_report >= 1.0:
                on_wait(
                    {
                        "state": "QUEUED",
                        "reason": (
                            "waiting for the single heavy-job slot"
                            if memory_ready and pressure_ready
                            else "waiting for host memory headroom"
                            if not memory_ready
                            else "waiting for host memory pressure to settle"
                        ),
                        "waited_seconds": round(now - started, 3),
                        "host": snapshot,
                        "limits": self.limits.to_dict(),
                    }
                )
                last_report = now
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                time.sleep(DEFAULT_QUEUE_POLL_SECONDS)
                continue
            except OSError as exc:
                handle.close()
                raise ResourceIsolationUnavailable(f"resource lock failed: {exc}") from exc
            snapshot = host_snapshot()
            available = snapshot.get("mem_available_bytes")
            full_pressure = (snapshot.get("memory_pressure") or {}).get("full_avg10")
            if available is None or full_pressure is None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()
                raise ResourceIsolationUnavailable(
                    "host memory telemetry became unavailable; refusing heavy job start"
                )
            if (
                available < self.limits.min_available_bytes
                or full_pressure > self.limits.max_full_pressure_avg10
            ):
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                time.sleep(DEFAULT_QUEUE_POLL_SECONDS)
                continue
            return ResourceLease(handle, path, time.monotonic() - started)

    @staticmethod
    def _filtered_environment(env: dict[str, str]) -> list[str]:
        assignments = []
        for key, value in sorted(env.items()):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                continue
            if _SENSITIVE_ENV_RE.search(key):
                continue
            if "\x00" in value:
                continue
            assignments.append(f"{key}={value}")
        return assignments

    def _bounded_environment(self, env: dict[str, str]) -> dict[str, str]:
        """Apply conservative numerical-tool thread defaults inside a job.

        The cgroup CPU quota is the hard boundary, but BLAS/OpenMP/Rayon and
        build tools can otherwise create many runnable threads before that
        quota is enforced. Keep their default at four workers (or the
        configured CPU quota when it is lower); an explicitly larger operator
        setting requires the same opt-in used for resource increases.
        """

        bounded = dict(env)
        raw = os.environ.get("PD_FLOW_NUM_THREADS", "4")
        try:
            requested = int(raw)
        except ValueError:
            requested = 4
        if requested < 1:
            requested = 4
        if requested > 4 and os.environ.get("PD_FLOW_RESOURCE_ALLOW_INCREASE") != "1":
            requested = 4
        quota_threads = max(1, (self.limits.cpu_quota_percent + 99) // 100)
        cap = min(requested, quota_threads)
        for key in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "BLIS_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
            "RAYON_NUM_THREADS",
            "CMAKE_BUILD_PARALLEL_LEVEL",
        ):
            current = bounded.get(key, "")
            try:
                current_count = int(current)
            except (TypeError, ValueError):
                current_count = 0
            if current_count < 1 or current_count > cap:
                bounded[key] = str(cap)
        return bounded

    def start(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        unit_name: str,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        cancel_event: threading.Event | None = None,
        on_wait: Callable[[dict[str, Any]], None] | None = None,
    ) -> ManagedProcess | None:
        if not command or any("\x00" in value for value in command):
            raise ResourceRunnerError("resource command must be a non-empty argv without NUL bytes")
        if timeout_seconds < 1 or timeout_seconds > 3600:
            raise ResourceConfigurationError("timeout must be between 1 and 3600 seconds")
        if timeout_seconds > DEFAULT_TIMEOUT_SECONDS and os.environ.get(
            "PD_FLOW_ALLOW_TIMEOUT_INCREASE"
        ) != "1":
            raise ResourceConfigurationError(
                "timeouts above 600 seconds require PD_FLOW_ALLOW_TIMEOUT_INCREASE=1"
            )
        if not _UNIT_RE.fullmatch(unit_name):
            raise ResourceRunnerError("invalid systemd unit name")
        if not cwd.is_dir():
            raise ResourceRunnerError(f"resource working directory is missing: {cwd}")
        lease = self.acquire(cancel_event=cancel_event, on_wait=on_wait)
        if lease is None:
            return None
        systemd_run = shutil.which("systemd-run")
        assert systemd_run is not None
        child_env = self._bounded_environment(env)
        child_env["PD_FLOW_RESOURCE_ACTIVE"] = "1"
        child = [
            "/usr/bin/env",
            "--ignore-environment",
            *self._filtered_environment(child_env),
            *command,
        ]
        argv = [
            systemd_run,
            "--user",
            "--quiet",
            "--wait",
            "--pipe",
            "--unit",
            unit_name,
            "--working-directory",
            str(cwd),
            "-p",
            f"MemoryMax={self.limits.memory_max_bytes}",
            "-p",
            f"MemoryHigh={self.limits.memory_high_bytes}",
            "-p",
            f"MemorySwapMax={self.limits.memory_swap_max_bytes}",
            "-p",
            f"CPUQuota={self.limits.cpu_quota_percent}%",
            "-p",
            "KillMode=control-group",
            "-p",
            "TimeoutStopSec=5s",
            "-p",
            f"RuntimeMaxSec={timeout_seconds}s",
            "--",
            *child,
        ]
        try:
            popen = subprocess.Popen(
                argv,
                cwd=str(cwd),
                env=os.environ.copy(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError:
            lease.release()
            raise
        managed = ManagedProcess(
            popen=popen,
            executor=self,
            lease=lease,
            unit_name=unit_name,
            started_at=time.monotonic(),
            initial_host=host_snapshot(),
            timeout_seconds=timeout_seconds,
        )
        # systemd may publish the transient unit a few milliseconds after
        # systemd-run has returned. Capture the cgroup early so short-lived
        # OOMs remain diagnosable after the service becomes inactive.
        # A transient service can be visible to systemd a little after the
        # client process is spawned. Do not stop probing merely because a very
        # short command has already exited; retaining the cgroup path is what
        # makes short-lived OOMs and peak metrics diagnosable.
        for _ in range(20):
            if managed.resource_metadata().get("cgroup"):
                break
            time.sleep(0.05)
        return managed

    @staticmethod
    def _systemctl(*args: str, timeout: float = 5) -> subprocess.CompletedProcess[str] | None:
        systemctl = shutil.which("systemctl")
        if not systemctl:
            return None
        try:
            return subprocess.run(
                [systemctl, "--user", *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

    def unit_cgroup(self, unit_name: str) -> str | None:
        result = self._systemctl("show", unit_name, "-p", "ControlGroup")
        if result is not None and result.returncode == 0:
            value = _parse_key_values(result.stdout).get("ControlGroup", "").strip()
            if value:
                return value

        # Very short services can be unloaded between the `systemd-run`
        # client returning and the first `systemctl show` call. The user
        # manager's app.slice is stable, and transient services have a
        # deterministic child path there. Retain that path for provenance;
        # cgroup files are still read opportunistically when they exist.
        parent = self._systemctl("show", "app.slice", "-p", "ControlGroup")
        if parent is None or parent.returncode != 0:
            return None
        parent_path = _parse_key_values(parent.stdout).get("ControlGroup", "").strip()
        if not parent_path:
            return None
        service = unit_name if unit_name.endswith(".service") else f"{unit_name}.service"
        return f"{parent_path.rstrip('/')}/{service}"

    def unit_metadata(
        self,
        unit_name: str,
        *,
        cgroup_path: str | None,
        initial_host: dict[str, Any],
        waited_seconds: float,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        result = self._systemctl(
            "show",
            unit_name,
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "Result",
            "-p",
            "ExecMainCode",
            "-p",
            "ExecMainStatus",
            "-p",
            "MemoryPeakEx",
            "-p",
            "MemoryCurrent",
            "-p",
            "MemorySwapCurrent",
            "-p",
            "CPUUsageNSec",
            "-p",
            "ControlGroup",
        )
        values = _parse_key_values(result.stdout if result and result.returncode == 0 else None)
        cgroup = cgroup_path or values.get("ControlGroup")
        events_raw = _read_cgroup_file(cgroup or "", "memory.events")
        memory_events: dict[str, str] = {}
        if events_raw:
            for line in events_raw.splitlines():
                parts = line.split()
                if len(parts) == 2:
                    memory_events[parts[0]] = parts[1]
        systemd_result = values.get("Result")
        oom = int(memory_events.get("oom_kill", "0") or 0) > 0 or systemd_result == "oom-kill"
        timed_out = systemd_result in {"timeout", "watchdog"}
        current_raw = _read_cgroup_file(cgroup or "", "memory.current")
        peak_raw = _read_cgroup_file(cgroup or "", "memory.peak")
        swap_raw = _read_cgroup_file(cgroup or "", "memory.swap.current")
        current_bytes = int(current_raw) if current_raw and current_raw.isdigit() else None
        peak_bytes = int(peak_raw) if peak_raw and peak_raw.isdigit() else None
        swap_bytes = int(swap_raw) if swap_raw and swap_raw.isdigit() else None
        return {
            "executor": "systemd-user-cgroup-v2",
            "unit": unit_name,
            "cgroup": cgroup,
            "limits": self.limits.to_dict(timeout_seconds=timeout_seconds),
            "queue_wait_seconds": round(waited_seconds, 3),
            "initial_host": initial_host,
            "final_host": host_snapshot(),
            "systemd": {
                "active_state": values.get("ActiveState"),
                "sub_state": values.get("SubState"),
                "result": values.get("Result"),
                "exec_main_code": values.get("ExecMainCode"),
                "exec_main_status": values.get("ExecMainStatus"),
                "memory_peak_bytes": peak_bytes or _parse_systemd_size(values.get("MemoryPeakEx")),
                "memory_current": current_bytes or _parse_systemd_size(values.get("MemoryCurrent")),
                "memory_swap_current": swap_bytes or _parse_systemd_size(values.get("MemorySwapCurrent")),
                "cpu_usage_ns": int(values["CPUUsageNSec"]) if values.get("CPUUsageNSec", "").isdigit() else None,
            },
            "memory_events": {key: int(value) for key, value in memory_events.items() if value.isdigit()},
            "resource_exhausted": oom,
            "resource_cause": "memory" if oom else "timeout" if timed_out else None,
        }

    def stop_unit(self, unit_name: str) -> None:
        self._systemctl("kill", "--kill-who=all", "--signal=TERM", unit_name, timeout=3)
        self._systemctl("stop", unit_name, timeout=7)

    def cleanup_unit(self, unit_name: str) -> None:
        self._systemctl("reset-failed", unit_name, timeout=3)
        self._systemctl("stop", unit_name, timeout=3)

    def run_command(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        label: str,
        log_path: Path,
        stream_output: bool = False,
    ) -> dict[str, Any]:
        if timeout_seconds < 1 or timeout_seconds > 3600:
            raise ResourceConfigurationError("timeout must be between 1 and 3600 seconds")
        if timeout_seconds > DEFAULT_TIMEOUT_SECONDS and os.environ.get(
            "PD_FLOW_ALLOW_TIMEOUT_INCREASE"
        ) != "1":
            raise ResourceConfigurationError(
                "timeouts above 600 seconds require PD_FLOW_ALLOW_TIMEOUT_INCREASE=1"
            )
        cancel = threading.Event()
        process = self.start(
            command,
            cwd=cwd,
            env=os.environ.copy(),
            unit_name=f"pdflow-cli-{os.getpid()}-{uuid.uuid4().hex[:12]}",
            timeout_seconds=timeout_seconds,
            cancel_event=cancel,
        )
        if process is None:
            return {"state": "CANCELLED", "reason": "cancelled before resource slot acquisition"}
        deadline = time.monotonic() + timeout_seconds
        selector = selectors.DefaultSelector()
        if process.stdout is not None:
            selector.register(process.stdout, selectors.EVENT_READ)
        with BoundedLog(
            log_path,
            max_bytes=self.limits.log_max_bytes,
            tail_bytes=self.limits.log_tail_bytes,
        ) as log:
            done = False
            forced_reason: str | None = None
            last_resource_sample = time.monotonic()
            while not done:
                if time.monotonic() >= deadline and forced_reason is None:
                    forced_reason = f"timeout after {timeout_seconds}s"
                    process.terminate("timeout")
                now = time.monotonic()
                if now - last_resource_sample >= 1.0:
                    process.resource_metadata()
                    last_resource_sample = now
                for key, _ in selector.select(timeout=0.2):
                    try:
                        chunk = os.read(key.fileobj.fileno(), 65536)
                    except OSError:
                        chunk = b""
                    if chunk:
                        log.append(chunk)
                        if stream_output:
                            sys.stdout.buffer.write(chunk)
                            sys.stdout.buffer.flush()
                    else:
                        done = True
                        selector.unregister(key.fileobj)
                if process.poll() is not None and not selector.get_map():
                    done = True
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate("forced cleanup")
                code = process.wait(timeout=5)
            resource = process.finish()
            log_tail = log.tail_text()
            refusal_reason = _controlled_refusal_reason(log_tail)
            if refusal_reason and not forced_reason and not resource.get("resource_exhausted"):
                state = "GAP"
            else:
                state = "FAILED" if forced_reason or code != 0 or resource.get("resource_exhausted") else "COMPLETED"
            reason = forced_reason
            if resource.get("resource_exhausted"):
                reason = "resource limit exceeded: memory cgroup OOM kill"
            elif resource.get("resource_cause") == "timeout" and not reason:
                reason = f"resource executor timeout after {timeout_seconds}s"
            elif refusal_reason:
                reason = refusal_reason
            elif state == "FAILED" and not reason:
                reason = f"process exited with code {code}"
            termination_cause = (
                "timeout"
                if forced_reason
                else "memory"
                if resource.get("resource_exhausted")
                else "refused"
                if refusal_reason
                else resource.get("resource_cause")
            )
            result = {
                "label": label,
                "state": state,
                "code": code,
                "reason": reason,
                "log_path": str(log_path),
                "log_bytes": log.bytes_written,
                "log_bytes_seen": log.bytes_seen,
                "log_truncated": log.truncated,
                "log_tail": log_tail,
                "resource": resource,
                "termination_cause": termination_cause,
            }
        selector.close()
        return result


def _default_cli_log(label: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-") or "job"
    log_dir = Path(os.environ.get("PD_FLOW_RESOURCE_LOG_DIR", "/tmp/pdflow-resource-logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{safe}-{int(time.time())}-{os.getpid()}.log"


def _cli_run(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    log_path = Path(args.log_file).resolve() if args.log_file else _default_cli_log(args.label)
    try:
        executor = ResourceExecutor(root)
        preflight = executor.preflight()
        if not preflight.get("available"):
            print(
                "PDflow heavy job refused: resource isolation unavailable: "
                + str(preflight.get("reason") or "unknown reason"),
                file=sys.stderr,
            )
            return 78
        print(
            "PDflow resource job "
            f"label={args.label} memory_max={executor.limits.memory_max_bytes} "
            f"memory_high={executor.limits.memory_high_bytes} "
            f"swap_max={executor.limits.memory_swap_max_bytes} "
            f"cpu_quota={executor.limits.cpu_quota_percent}% timeout={args.timeout}s",
            file=sys.stderr,
        )
        result = executor.run_command(
            args.command,
            cwd=root,
            timeout_seconds=args.timeout,
            label=args.label,
            log_path=log_path,
        )
        print("PDflow resource result " + json.dumps(result, sort_keys=True), file=sys.stderr)
        if result.get("state") != "COMPLETED" and result.get("log_tail"):
            print("PDflow resource failure log tail (bounded):", file=sys.stderr)
            print(str(result["log_tail"])[-executor.limits.log_tail_bytes :], file=sys.stderr)
        return int(result.get("code") or (1 if result.get("state") != "COMPLETED" else 0))
    except ResourceRunnerError as exc:
        print(f"PDflow heavy job refused: {exc}", file=sys.stderr)
        return 78


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="bounded PDflow Linux resource executor")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    run = sub.add_parser("run", help="run one command in the shared cgroup slot")
    run.add_argument("--label", required=True)
    run.add_argument("--cwd", default=str(Path.cwd()))
    run.add_argument("--timeout", type=int, default=600)
    run.add_argument("--log-file")
    run.add_argument("command", nargs=argparse.REMAINDER)
    status = sub.add_parser("status", help="print resource backend status")
    status.add_argument("--cwd", default=str(Path.cwd()))
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.subcommand == "status":
        try:
            print(json.dumps(ResourceExecutor(Path(args.cwd)).describe(), sort_keys=True))
            return 0
        except ResourceRunnerError as exc:
            print(json.dumps({"available": False, "reason": str(exc)}, sort_keys=True))
            return 78
    if not args.command:
        parser.error("run requires a command after --")
    if args.command[0] == "--":
        args.command = args.command[1:]
    if args.timeout < 1 or args.timeout > 3600:
        parser.error("--timeout must be between 1 and 3600 seconds")
    return _cli_run(args)


if __name__ == "__main__":
    raise SystemExit(main())

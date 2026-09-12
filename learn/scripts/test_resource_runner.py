"""Local acceptance tests for the bounded Linux resource executor."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn"))

from pdflow_agent.resource_runner import (  # noqa: E402
    ResourceConfigurationError,
    ResourceExecutor,
    ResourceIsolationUnavailable,
    ResourceLimits,
)


def wait_for(path: Path, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return True
        time.sleep(0.05)
    return path.is_file()


def command_result(runner: ResourceExecutor, directory: Path, name: str, command: list[str]):
    return runner.run_command(
        command,
        cwd=directory,
        timeout_seconds=30,
        label=name,
        log_path=directory / f"{name}.log",
    )


def main() -> None:
    status_runner = ResourceExecutor(ROOT)
    status = status_runner.describe()
    assert status["available"] is True, status
    assert status["isolation"] == "systemd-user-cgroup-v2"
    assert status["queue"] == "single-heavy-slot"
    assert status["limits"]["memory_max_bytes"] == 6 * 1024**3
    assert status["limits"]["memory_high_bytes"] == 5 * 1024**3
    assert status["limits"]["memory_swap_max_bytes"] == 512 * 1024**2
    assert status["limits"]["cpu_quota_percent"] == 400
    assert status["limits"]["min_available_bytes"] == 4 * 1024**3
    assert status["limits"]["max_full_pressure_avg10"] == 10.0

    with patch("pdflow_agent.resource_runner.shutil.which", return_value=None):
        unavailable = ResourceExecutor(ROOT).preflight(force=True)
    assert unavailable["available"] is False
    assert "systemd" in unavailable["reason"]

    old_max = os.environ.pop("PD_FLOW_RESOURCE_MEMORY_MAX", None)
    old_allow = os.environ.pop("PD_FLOW_RESOURCE_ALLOW_INCREASE", None)
    try:
        os.environ["PD_FLOW_RESOURCE_MEMORY_MAX"] = "7GiB"
        try:
            ResourceLimits.from_environment()
        except ResourceConfigurationError:
            pass
        else:
            raise AssertionError("unsafe resource increase was accepted")
        os.environ["PD_FLOW_RESOURCE_ALLOW_INCREASE"] = "1"
        assert ResourceLimits.from_environment().memory_max_bytes == 7 * 1024**3
    finally:
        if old_max is None:
            os.environ.pop("PD_FLOW_RESOURCE_MEMORY_MAX", None)
        else:
            os.environ["PD_FLOW_RESOURCE_MEMORY_MAX"] = old_max
        if old_allow is None:
            os.environ.pop("PD_FLOW_RESOURCE_ALLOW_INCREASE", None)
        else:
            os.environ["PD_FLOW_RESOURCE_ALLOW_INCREASE"] = old_allow

    with patch.object(status_runner, "_ensure_available"):
        with patch(
            "pdflow_agent.resource_runner.host_snapshot",
            return_value={
                "mem_available_bytes": None,
                "memory_pressure": {"some_avg10": None, "full_avg10": None},
            },
        ):
            try:
                status_runner.acquire()
            except ResourceIsolationUnavailable as exc:
                assert "cannot be verified" in str(exc)
            else:
                raise AssertionError("heavy execution started without host telemetry")

    with tempfile.TemporaryDirectory(prefix="pdflow-resource-test-") as raw:
        directory = Path(raw)
        echo = command_result(
            status_runner,
            directory,
            "echo",
            [sys.executable, "-c", "print('resource runner ok')"],
        )
        assert echo["state"] == "COMPLETED", echo
        assert echo["code"] == 0
        assert echo["resource"]["cgroup"]
        assert echo["resource"]["resource_exhausted"] is False
        assert (directory / "echo.log").read_text(encoding="utf-8").strip() == "resource runner ok"

        thread_probe = command_result(
            status_runner,
            directory,
            "thread-probe",
            [
                sys.executable,
                "-c",
                "import os; assert int(os.environ['OMP_NUM_THREADS']) <= 4; "
                "assert int(os.environ['OPENBLAS_NUM_THREADS']) <= 4; print('thread cap ok')",
            ],
        )
        assert thread_probe["state"] == "COMPLETED", thread_probe

        log_limits = ResourceLimits(
            memory_max_bytes=6 * 1024**3,
            memory_high_bytes=5 * 1024**3,
            memory_swap_max_bytes=512 * 1024**2,
            cpu_quota_percent=400,
            min_available_bytes=4 * 1024**3,
            log_max_bytes=8192,
            log_tail_bytes=1024,
        )
        log_runner = ResourceExecutor(ROOT, limits=log_limits)
        noisy = command_result(
            log_runner,
            directory,
            "bounded-log",
            [
                sys.executable,
                "-c",
                "import sys; [sys.stdout.write('x'*200+'\\n') for _ in range(2000)]",
            ],
        )
        assert noisy["state"] == "COMPLETED", noisy
        assert noisy["log_bytes"] <= 8192
        assert noisy["log_bytes_seen"] > noisy["log_bytes"]
        assert noisy["log_truncated"] is True

        refused = command_result(
            log_runner,
            directory,
            "bounded-refusal",
            [
                "/bin/sh",
                "-c",
                "printf '%s\\n' 'REFUSED: protected fixture finish' >&2; exit 2",
            ],
        )
        assert refused["state"] == "GAP", refused
        assert refused["termination_cause"] == "refused", refused
        assert refused["reason"] == "REFUSED: protected fixture finish", refused

        small_limits = ResourceLimits(
            memory_max_bytes=64 * 1024**2,
            memory_high_bytes=64 * 1024**2,
            memory_swap_max_bytes=0,
            cpu_quota_percent=100,
            min_available_bytes=4 * 1024**3,
            log_max_bytes=1024 * 1024,
            log_tail_bytes=4096,
        )
        small_runner = ResourceExecutor(ROOT, limits=small_limits)
        oom = command_result(
            small_runner,
            directory,
            "bounded-oom",
            [
                sys.executable,
                "-c",
                "x=bytearray(96*1024*1024); [x.__setitem__(i, 1) for i in range(0, len(x), 4096)]",
            ],
        )
        assert oom["state"] == "FAILED", oom
        assert oom["resource"]["resource_exhausted"] is True, oom
        assert oom["reason"] == "resource limit exceeded: memory cgroup OOM kill", oom
        assert oom["resource"]["unit"].startswith("pdflow-cli-")

        timed = ResourceExecutor(ROOT)
        timeout_result = timed.run_command(
            ["/bin/sh", "-c", "sleep 30"],
            cwd=directory,
            timeout_seconds=1,
            label="bounded-timeout",
            log_path=directory / "bounded-timeout.log",
        )
        assert timeout_result["state"] == "FAILED", timeout_result
        assert timeout_result["reason"] in {
            "timeout after 1s",
            "resource executor timeout after 1s",
        }, timeout_result
        assert timeout_result["resource"]["limits"]["timeout_seconds"] == 1
        assert timeout_result["resource"]["termination_requested"] in {None, "timeout"}
        assert timeout_result["termination_cause"] == "timeout", timeout_result
        assert timeout_result["resource"]["resource_cause"] == "timeout", timeout_result

        sampled = timed.run_command(
            ["/bin/sh", "-c", "sleep 2"],
            cwd=directory,
            timeout_seconds=10,
            label="bounded-metrics",
            log_path=directory / "bounded-metrics.log",
        )
        assert sampled["state"] == "COMPLETED", sampled
        assert sampled["resource"]["systemd"]["memory_peak_bytes"] is not None, sampled

        child_pid_file = directory / "child.pid"
        cancelled_runner = ResourceExecutor(ROOT)
        cancelled = cancelled_runner.start(
            ["/bin/sh", "-c", "sleep 30 & printf '%s\\n' $! > child.pid; wait"],
            cwd=directory,
            env=os.environ.copy(),
            unit_name="pdflow-cancel-acceptance",
        )
        assert cancelled is not None
        assert wait_for(child_pid_file)
        child_pid = int(child_pid_file.read_text(encoding="utf-8").strip())
        cancelled.terminate("cancelled by user")
        cancelled.wait(timeout=5)
        cancelled_resource = cancelled.finish()
        assert cancelled_resource["termination_requested"] == "cancelled by user"
        assert cancelled.poll() is not None
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError("cgroup cancellation left a descendant alive")

        concurrent_runner = ResourceExecutor(ROOT)
        results: list[dict] = []
        results_lock = threading.Lock()

        def run_serialized(index: int) -> None:
            result = concurrent_runner.run_command(
                [sys.executable, "-c", "import time; time.sleep(0.8)"],
                cwd=directory,
                timeout_seconds=30,
                label=f"serial-{index}",
                log_path=directory / f"serial-{index}.log",
            )
            with results_lock:
                results.append(result)

        started = time.monotonic()
        threads = [threading.Thread(target=run_serialized, args=(index,)) for index in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        elapsed = time.monotonic() - started
        assert len(results) == 2, results
        assert all(result["state"] == "COMPLETED" for result in results), results
        assert elapsed >= 1.4, elapsed

    print("OK test_resource_runner")


if __name__ == "__main__":
    main()

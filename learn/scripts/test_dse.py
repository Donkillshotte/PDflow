#!/usr/bin/env python3
"""DSE contracts: layered knobs, Pareto, e-graph, SSK-GP, attribution, F1 equiv.

Entrypoint for the D.1–D.5 split. Same ``ok`` messages as the former monolith.
Live F4 stays last — one process, one heavy job.
"""

from __future__ import annotations

import sys
import os
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn"))


def _resource_guarded() -> bool:
    """Return true only when this test is inside the verified heavy-job cgroup."""

    guard = _ROOT / "scripts" / "resource_guard.sh"
    if not guard.is_file():
        return False
    return (
        subprocess.run(
            [str(guard)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


# This test intentionally exercises the live F4 worker and is commonly run
# directly by developers.  Keep that entry point subject to the same cgroup,
# timeout, log, and single-slot policy as the production DSE launcher.  The
# environment flag only prevents an infinite re-exec loop; the guard itself
# still validates the kernel cgroup path and cannot be bypassed by the flag.
if not _resource_guarded() and os.environ.get("PD_FLOW_TEST_DSE_REEXEC") != "1":
    child_env = os.environ.copy()
    child_env["PD_FLOW_TEST_DSE_REEXEC"] = "1"
    raise SystemExit(
        subprocess.run(
            [
                str(_ROOT / "scripts" / "run_resource_job.sh"),
                "test-dse",
                sys.executable,
                str(Path(__file__).resolve()),
            ],
            cwd=str(_ROOT),
            env=child_env,
            check=False,
        ).returncode
    )


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    from test_dse_metrics import check_metrics

    check_metrics(check)

    from test_dse_memory import check_memory

    _mem = check_memory(check, root=_ROOT)
    mem, mem2 = _mem["mem"], _mem["mem2"]

    from test_dse_planner import check_planner

    check_planner(check, root=_ROOT, mem=mem, mem2=mem2)

    from test_dse_steer import check_steer

    check_steer(check)

    from test_dse_campaign import check_campaign

    check_campaign(check)

    from test_dse_next import check_next_level

    check_next_level(check, root=_ROOT)

    from test_dse_live_f4 import check_live_f4

    check_live_f4(check, root=_ROOT)

    print("ALL test_dse PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

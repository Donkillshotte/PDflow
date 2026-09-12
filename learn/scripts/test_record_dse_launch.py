#!/usr/bin/env python3
"""The DSE app snapshot is current-only and schema-driven."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from record_dse_launch import snapshot_from_report  # noqa: E402


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    shot = snapshot_from_report(
        {
            "ok": True,
            "variant": "fixture",
            "design_id": "toy",
            "run_id": "run-fixture",
            "n_candidates": 3,
            "n_f4": 2,
            "winning_ir_pdn_mv": 1.705,
            "spent_s": 12.0,
        }
    )
    check(shot["kind"] == "dse_live_run", "live snapshot kind")
    check(shot["comparison_scope"] == "same-live-invocation", "same-run scope")
    check(shot["run_id"] == "run-fixture", "run id is preserved")
    check(shot["n_candidates"] == 3, "candidate count")
    check(shot["winning_ir_pdn_mv"] == 1.705, "current IR value")
    source = (_SCRIPTS / "record_dse_launch.py").read_text()
    check("comparison_scope" in source, "snapshot requires an explicit comparison scope")
    print("ALL test_record_dse_launch PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

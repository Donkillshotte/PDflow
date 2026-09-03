#!/usr/bin/env python3
"""ECO propose is allowed on flowlab; apply is not. DSE never owns signoff."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "learn/scripts"


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    env = os.environ.copy()
    env["FLOW_VARIANT"] = "flowlab"
    env["ECO_MODE"] = "propose"
    env["PYTHONPATH"] = f"{ROOT}/learn:{SCRIPTS}"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "run_eco.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    check(proc.returncode == 0, "eco propose exits 0 on flowlab")
    report = json.loads((ROOT / "learn/sim/reports/eco_flowlab.json").read_text())
    check(report.get("kind") == "eco", "eco kind")
    check(report.get("mode") == "propose", "eco mode propose")
    check(report.get("signoff") is False, "propose does not claim signoff")
    check("run_signoff_all" in str(report.get("signoff_required")), "signoff_all required after ECO")
    check(report.get("locked") is True, "flowlab is locked")
    check(isinstance(report.get("proposed"), list) and report["proposed"], "proposed steps present")

    env["ECO_MODE"] = "apply"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "run_eco.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    check(proc.returncode != 0, "eco apply refused on flowlab")
    applied = json.loads((ROOT / "learn/sim/reports/eco_apply_flowlab.json").read_text())
    propose_still = json.loads((ROOT / "learn/sim/reports/eco_flowlab.json").read_text())
    check(propose_still.get("mode") == "propose", "apply does not overwrite the propose report")
    check(applied.get("ok") is False, "apply ok is false on locked variant")
    check("refuse" in str(applied.get("error") or "").lower(), "apply error names refuse")

    src = (SCRIPTS / "run_eco.py").read_text()
    check("eco_repair.tcl" in src, "apply points at eco_repair.tcl")
    check(src.find("subprocess.run") > src.find("run_signoff_all.sh"), "signoff_all is only named, not launched")
    print("ALL test_eco PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

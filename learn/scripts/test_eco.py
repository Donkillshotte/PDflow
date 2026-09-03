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
    check("ECO_LIB" in src and "NangateOpenCellLibrary_typical.lib" in src, "apply sets ECO_LIB")
    check("ECO_SDC" in src, "apply sets ECO_SDC")
    check("ECO_RC" in src and "setRC.tcl" in src, "apply sources platform setRC")
    check(src.find("subprocess.run") > src.find("run_signoff_all.sh"), "signoff_all is only named, not launched")
    tcl = (SCRIPTS / "eco_repair.tcl").read_text()
    check("read_liberty" in tcl, "repair tcl reads liberty")
    check("read_sdc" in tcl, "repair tcl reads SDC")
    check("ECO_RC" in tcl, "repair tcl sources ECO_RC")
    check("remove_fillers" in tcl and "filler_placement" in tcl, "repair tcl refills after DPL")

    live = ROOT / "learn/sim/reports/eco_apply_eco_scratch.json"
    if live.is_file():
        scratch = json.loads(live.read_text())
        check(scratch.get("mode") == "apply", "scratch apply report is apply")
        check(scratch.get("signoff") is False, "scratch apply does not claim signoff")
        check(scratch.get("ok") is True, "scratch apply wrote sidecar")
        check("run_signoff_all" in str(scratch.get("signoff_required")), "scratch still requires signoff_all")
        out_odb = Path(scratch.get("output_odb") or "")
        check(out_odb.is_file(), "scratch sidecar ODB exists")
        flowlab = ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb"
        check(flowlab.is_file(), "flowlab 6_final.odb still present")
        check(out_odb.resolve() != flowlab.resolve(), "sidecar is not the locked flowlab ODB")
    print("ALL test_eco PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

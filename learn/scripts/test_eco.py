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
    check("write_verilog" in tcl, "repair tcl writes sidecar verilog")
    check("write_def" in tcl, "repair tcl writes DEF")
    check("write_cdl" in tcl, "repair tcl writes CDL")
    check("extract_parasitics" in tcl, "repair tcl extracts SPEF when RCX exists")
    check((SCRIPTS / "eco_stream_gds.py").is_file(), "GDS stream helper exists")
    check("eco_stream_gds.py" in src, "apply streams GDS after DEF")
    check("6_final.gds" in src, "apply installs 6_final.gds on unlocked copy")
    check("run_signoff_all.sh" not in src[src.find("subprocess.run"):src.find("subprocess.run") + 400], "first OpenROAD launch is not signoff_all")

    studio_run = (ROOT / "studio/src/lib/run.ts").read_text()
    check('"eco_apply"' in studio_run, "Studio allows eco_apply")
    check('"eco_close"' in studio_run, "Studio allows eco_close")
    check('env.FLOW_VARIANT = "eco_scratch"' in studio_run, "Studio apply/close force eco_scratch")
    check('env.ECO_MODE = "apply"' in studio_run, "Studio apply sets ECO_MODE")
    check("run_signoff_all.sh" in studio_run, "Studio close maps to signoff_all")
    panel = (ROOT / "studio/src/components/flowlab/EcoPanel.tsx").read_text()
    check('onRun("eco_apply"' in panel, "EcoPanel can launch apply")
    check('onRun("eco_close"' in panel, "EcoPanel can launch close")
    check("signoff_all" in panel, "EcoPanel names signoff_all as close")
    finish = (ROOT / "studio/src/components/flowlab/FlowLabSignoff.tsx").read_text()
    check("LabBench" not in finish, "finish loop does not mix LabBench")
    pkg = (ROOT / "studio/src/components/PkgHubPanel.tsx").read_text()
    check("LabBench" not in pkg and "DsePanel" not in pkg, "PKG hub does not embed Lab/DSE")
    vis = (ROOT / "studio/src/components/flowlab/FlowLabPhaseVisual.tsx").read_text()
    check("LabBench" not in vis and "DsePanel" not in vis, "PKG phase visual does not embed Lab/DSE")
    check("fl-signoff-more" in finish, "individual STA/DRC/LVS scripts are behind details")
    check("eco_scratch" in finish, "finish copy names eco_scratch")
    sig_ts = (ROOT / "studio/src/lib/signoff.ts").read_text()
    check("leftoverMustConnectDetail" in sig_ts, "equivalence pillar names leftover")
    check("Nangate split wells" in sig_ts, "leftover names the PDK cause")
    check("IrMeshLedger" in finish, "finish power shows IR mesh ledger")
    check('href="/lab"' in finish, "finish DSE points at /lab")
    console = (ROOT / "studio/src/components/LiveRunConsole.tsx").read_text()
    check("optgroup" in console and "run-picker" in console, "Tools runner is a grouped select")
    check("POST_FINISH_CHIPS" not in console, "chip wall list is gone")
    report_api = (ROOT / "studio/src/app/api/report/route.ts").read_text()
    check("power_signoff_flowlab.json" in report_api, "report API serves the IR mesh ledger")

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
        if scratch.get("ok"):
            check("gds" in (scratch.get("rewrote") or []), "scratch apply streamed GDS")
            check("verilog" in (scratch.get("rewrote") or []), "scratch apply lists verilog")
            gds = Path(scratch.get("output_gds") or "")
            check(gds.is_file(), "scratch GDS exists")
            flowlab_gds = ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.gds"
            if gds.is_file() and flowlab_gds.is_file():
                check(gds.resolve() != flowlab_gds.resolve(), "ECO GDS is not the locked flowlab GDS")
            installed = Path(scratch.get("results_dir") or "") / "6_final.gds"
            check(installed.is_file(), "unlocked results/6_final.gds installed")
            close = ROOT / "learn/sim/reports/signoff_all_eco_scratch.json"
            if close.is_file():
                sig = json.loads(close.read_text())
                check(sig.get("kind") == "signoff_all", "eco_scratch close is signoff_all")
                check(sig.get("ok") is True, "eco_scratch signoff_all ok")
                check(sig.get("variant") == "eco_scratch", "close is not flowlab")
                check(scratch.get("signoff") is False, "apply still does not claim the close")
    print("ALL test_eco PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

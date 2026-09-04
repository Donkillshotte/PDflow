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
    sys.path.insert(0, str(SCRIPTS))
    from run_eco import _plan

    blind = next(s for s in _plan({}) if s.get("args") == "-setup")
    check(blind.get("enabled") is False, "ECO does not propose setup repair without STA")
    check("without STA" in str(blind.get("reason")), "ECO names the missing STA")
    late = next(s for s in _plan({"timing": {"wns_ns": -0.02}}) if s.get("args") == "-setup")
    check(late.get("enabled") is True, "ECO still proposes setup when WNS is negative")

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
    check("ECO_SPEF_IN" in tcl and "read_spef" in tcl, "repair tcl can load the source SPEF")
    # Compare command positions, not comments (line 25 mentions repair_timing).
    spef_cmd = tcl.find("read_spef $::env(ECO_SPEF_IN)")
    setup_cmd = tcl.find("repair_timing -setup")
    check(spef_cmd >= 0 and setup_cmd >= 0 and spef_cmd < setup_cmd, "repair tcl reads SPEF before setup repair")
    check("-skip_buffering" in tcl and "sizeup,swap" in tcl, "post-route ECO skips BufferMove (needs GRT)")
    check("ECO_FASTROUTE" in tcl and "global_route" in tcl, "repair tcl initializes GRT before size-up")
    check("detailed_route" in tcl and "design_is_routed" in tcl, "repair tcl detailed-routes before writing 6_final")
    check("ECO_RESTORE_SOURCE" in tcl, "repair tcl restores source ODB if size-up is not routed")
    check("file copy -force" in tcl, "unrouted restore copies the input ODB file (read_db cannot reload)")
    check("exit 1" not in tcl.split("design_is_routed")[1].split("write_db")[0], "unrouted size-up does not write a broken 6_final")
    check("ECO_RESTORE_SOURCE" in src, "apply report names a restored source")
    check("ECO_SPEF_IN" in src, "apply passes the source 6_final.spef")
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
    check("sta_signoff" not in pkg and "drc_signoff" not in pkg and "lvs_signoff" not in pkg, "PKG hub does not list STA/DRC/LVS")
    check("signoff_all" not in pkg and "chip_pdn_ir" not in pkg, "PKG hub does not host signoff_all or chip IR")
    check("power_chain" not in pkg, "PKG hub does not run the power chain")
    check("system_pdn" in pkg and "signoff_phase2" in pkg, "PKG hub keeps System PDN and Phase 2")
    check('runAction("system_pdn"' in pkg, "PKG hub can run System PDN")
    pkg_page = (ROOT / "studio/src/app/pkg/page.tsx").read_text()
    check("/flow?phase=pkg" not in pkg, "PKG hub does not deep-link a FlowLab PKG phase")
    check("signoff_all" in pkg_page and "finish" in pkg_page, "PKG page points four-pillar close at finish")
    check("/flow?phase=pkg" not in pkg_page, "PKG page does not deep-link a FlowLab PKG phase")
    check("run_power_chain.sh" not in pkg_page and "run_chip_pdn_ir.sh" not in pkg_page, "PKG page does not list finish-owned IR scripts")
    vis = (ROOT / "studio/src/components/flowlab/FlowLabPhaseVisual.tsx").read_text()
    check(">Lab viewport<" not in vis, "FlowLab viewport is not labeled Lab")
    check(">FlowLab viewport<" in vis, "phase visual names the FlowLab viewport")
    check("LabBench" not in vis and "DsePanel" not in vis, "phase visual does not embed Lab/DSE")
    check("DieCanvas" not in vis, "unused die canvas is gone")
    flow = (ROOT / "studio/src/components/FlowLab.tsx").read_text()
    check('phaseId !== "finish"' in flow and "FlowLabPowerChain" in flow, "finish does not remount the power-chain strip on finish")
    check("RTL → PKG chain" not in (ROOT / "studio/src/components/flowlab/FlowLabPowerChain.tsx").read_text(), "power chain heading is not RTL → PKG")
    check("SPICE chain RTL→PKG" not in (ROOT / "studio/src/lib/materials-data.ts").read_text(), "materials catalog does not title the chain RTL→PKG")
    jobs_ts = (ROOT / "studio/src/lib/jobs.ts").read_text()
    check("reconcileOrphanJobs" in jobs_ts, "job history marks orphan running cooks")
    check("orphan running job" in jobs_ts, "orphan running jobs get an error stamp")
    check('phases={CLOSE_PHASES}' in flow, "FlowLab pipeline is RTL → finish, not nine phases")
    check("CLOSE_PHASES.findIndex" in flow, "next-phase walk is RTL → finish only")
    check("PHASE_IDS.indexOf(phaseId) + 1" not in flow, "next-phase walk does not step onto PKG")
    check("Open PKG" in flow and 'href="/pkg"' in flow, "finish next banner opens /pkg, not a FlowLab PKG phase")
    check("action === phase.action" in flow, "next banner only after the phase action, not ECO/STA")
    check('router.replace("/pkg")' in flow, "stale /flow?phase=pkg opens /pkg")
    check("CLOSE_PHASES" in flow, "FlowLab progress counts RTL → finish, not PKG")
    check("ninth signoff pillar" in flow, "FlowLab hero says PKG is not a signoff pillar")
    phases = (ROOT / "studio/src/components/flowlab/phases.ts").read_text()
    check("CLOSE_PHASES" in phases, "phases.ts exports CLOSE_PHASES without PKG")
    pipe = (ROOT / "studio/src/components/flowlab/FlowLabPipeline.tsx").read_text()
    check('p.id === "pkg"' not in pipe, "pipeline has no PKG step")
    check("Pipeline RTL → finish" in pipe, "pipeline aria is RTL → finish")
    check('mode="full"' not in flow, "FlowLab does not dump finish signoff onto PKG")
    check("Istanze" not in vis and "verificato" not in vis, "phase visual is English")
    ops = (ROOT / "studio/src/components/OpsDashboard.tsx").read_text()
    check("Azione" not in ops and "Stato" not in ops and "Inizio" not in ops, "job history headers are English")
    wave = (ROOT / "studio/src/components/flowlab/RtlWaveformVisual.tsx").read_text()
    check("Pronto" not in wave and "Cursore" not in wave, "RTL waveform stats are English")
    check("finestra" not in wave and "Fit tempo" not in wave, "RTL waveform toolbar is English")
    canvas = (ROOT / "studio/src/components/flowlab/FlowLabLayoutCanvas.tsx").read_text()
    check("PNG da ODB" not in canvas and "Genero" not in canvas and "Avvio" not in canvas, "layout canvas buttons are English")
    inspect = (ROOT / "studio/src/components/InspectPanel.tsx").read_text()
    check("Avvio" not in inspect, "inspect viewer button is English")
    layers = (ROOT / "studio/src/lib/layoutStudio.ts").read_text()
    check("Siti standard-cell" not in layers and "Heatmap tensione" not in layers, "layer roles are English")
    check("Physically-aware DSE" not in (ROOT / "studio/src/lib/suite.ts").read_text(), "suite names DSE as proposer")
    dse_panel = (ROOT / "studio/src/components/flowlab/DsePanel.tsx").read_text()
    chips_at = dse_panel.find("lb-chips")
    details_at = dse_panel.find("Lab IR highlights / raw tape")
    check(chips_at > 0 and details_at > 0 and chips_at > details_at, "DSE IR chip wall is behind details")
    check('href: "/lab"' in (ROOT / "studio/src/lib/suite.ts").read_text(), "suite DSE points at /lab")
    dse_hook = (ROOT / "studio/src/lib/suite.ts").read_text().split('id: "dse"')[1].split("},")[0]
    check("action:" not in dse_hook, "suite DSE hook has no Tools run action")
    hub = (ROOT / "studio/src/components/SuiteHub.tsx").read_text()
    check('h.href !== "/lab"' in hub and 'h.href !== "/pkg"' in hub, "SuiteHub does not Run Lab/PKG hooks on Tools")
    check("/tools?tab=run&action=${h.action}" in hub, "other hooks can still Run on Tools")
    check("fl-signoff-more" in finish, "individual STA/DRC/LVS scripts are behind details")
    check("STA IR-aware overlay (lab" not in finish, "STA IR-aware is on the finish close, not a collapsed lab details")
    check(
        "<StaIrAwarePanel" in finish.split("Individual STA")[0],
        "STA IR-aware panel sits with the matrix, not inside the script dump",
    )
    check("eco_scratch" in finish, "finish copy names eco_scratch")
    sig_ts = (ROOT / "studio/src/lib/signoff.ts").read_text()
    check("leftoverMustConnectDetail" in sig_ts, "equivalence pillar names leftover")
    check("Nangate split wells" in sig_ts, "leftover names the PDK cause")
    check("IrMeshLedger" in finish, "finish power shows IR mesh ledger")
    check("DynamicIrHeatmap" in finish, "finish power shows Dynamic IR heatmap")
    check('id="ir"' in finish, "finish has the #ir power close")
    check('mode === "pkg"' not in finish, "FlowLab signoff has no PKG workbench mode")
    power_block = finish.split("const POWER_ACTIONS")[1].split("const FINISH_ACTIONS")[0]
    check('"system_pdn"' not in power_block, "finish power scripts do not launch System PDN")
    check('"power_chain"' not in power_block, "finish power scripts do not launch the SPICE chain")
    phases = (ROOT / "studio/src/components/flowlab/phases.ts").read_text()
    check('id: "pkg"' not in phases, "FlowLab PHASES has no PKG phase")
    flowlab_ts = (ROOT / "studio/src/lib/flowlab.ts").read_text()
    flow_phases = flowlab_ts.split("export const FLOW_PHASES")[1].split("export type FlowPhaseId")[0]
    check('id: "pkg"' not in flow_phases, "FLOW_PHASES status has no PKG stage")
    check('id: "pkg"' not in flow, "FlowLab workbench has no PKG phase branch")
    check('mode="pkg"' not in flow, "FlowLab does not mount a PKG signoff workbench")
    lesson_pc = (ROOT / "studio/src/components/LessonPowerChainPanel.tsx").read_text()
    check('p === "pkg" ? "/pkg"' in lesson_pc, "lesson power chain does not open /flow?phase=pkg")
    check('flowlabPhases: ["finish"]' in (ROOT / "studio/src/lib/powerChainLessons.ts").read_text(), "lesson 07 FlowLab phases are finish only")
    check('href: "/lab#dse"' in (ROOT / "studio/src/lib/open.ts").read_text(), "Open palette sends DSE to /lab")
    check("initialSystem" in pkg, "PKG hub can hydrate System PDN from the server")
    check("readReport" in pkg_page, "PKG page reads reports before first paint")
    matrix = (ROOT / "studio/src/components/flowlab/SignoffMatrixPanel.tsx").read_text()
    check("showPhase2" in matrix, "signoff matrix can hide Phase 2")
    check("showPhase2={false}" in finish or "showPhase2 =" in matrix, "finish matrix defaults Phase 2 off")
    check("leftover must-connect" in panel, "EcoPanel close names leftover")
    check('href="/lab"' in finish, "finish DSE points at /lab")
    console = (ROOT / "studio/src/components/LiveRunConsole.tsx").read_text()
    check("optgroup" in console and "run-picker" in console, "Tools runner is a grouped select")
    check("POST_FINISH_CHIPS" not in console, "chip wall list is gone")
    check('{ id: "dse"' not in console, "Tools runner does not launch DSE")
    heatmap = (ROOT / "studio/src/components/flowlab/DynamicIrHeatmap.tsx").read_text()
    check("Solver / EM / activity (lab)" in heatmap, "Dynamic IR keeps solver gauges behind details")
    check("different extract" in heatmap, "Dynamic IR names gold as another mesh")
    check("dynamic_ir_${variant}_direct.json" in heatmap, "heatmap loads current_run _direct.json")
    check("dynamic_ir_${variant}.json" not in heatmap, "heatmap does not treat the gold sentinel as current_run")
    check("Report missing" not in heatmap, "heatmap does not call gold-only a missing report")
    report_api = (ROOT / "studio/src/app/api/report/route.ts").read_text()
    check("power_signoff_flowlab.json" in report_api, "report API serves the IR mesh ledger")

    live = ROOT / "learn/sim/reports/eco_apply_eco_scratch.json"
    if live.is_file():
        scratch = json.loads(live.read_text())
        check(scratch.get("mode") == "apply", "scratch apply report is apply")
        check(scratch.get("signoff") is False, "scratch apply does not claim signoff")
        check(scratch.get("ok") is True, "scratch apply wrote sidecar")
        check("run_signoff_all" in str(scratch.get("signoff_required")), "scratch still requires signoff_all")
        if scratch.get("repaired") is False:
            check(bool(scratch.get("leftover")), "unrepaired apply names leftover")
            check("signoff_all" in str(scratch.get("summary")), "unrepaired apply still requires signoff_all")
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
                leftover = sig.get("leftover") or {}
                check(int(leftover.get("must_connect") or 0) == 2, "eco close leftover is 2")
                check("DFF_X2" in (leftover.get("circuits") or []), "eco close leftover is DFF_X2")
                check((sig.get("ir_mesh_ledger") or {}).get("comparable") is False, "eco close IR ledger not comparable")
                check(scratch.get("signoff") is False, "apply still does not claim the close")
    print("ALL test_eco PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Signoff reports must not fake a pass. Educational GAP stays GAP."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def load(name: str) -> dict:
    path = REPORTS / name
    check(path.is_file(), f"{name} exists")
    return json.loads(path.read_text())


def main() -> int:
    gold = load("dynamic_ir_flowlab.json")
    check(gold.get("gold") is True, "gold sentinel still gold")
    check(abs(float(gold["worst_droop_mv"]) - 45.298) < 0.02, "gold droop 45.298")
    check(gold.get("ok") is not True, "gold sentinel has no ok pass bit")
    current = load("dynamic_ir_flowlab_direct.json")
    check(current.get("ok") is True, "current_run direct report is ok")
    check(current.get("gold") is not True, "current_run is not the gold sentinel")
    cur_mv = float((current.get("dynamic") or {}).get("worst_droop") or 0) * 1e3
    check(abs(cur_mv - 6.075) < 0.02, "current_run droop is ~6.075 mV")
    story = (ROOT / "studio/src/lib/story.ts").read_text()
    check("dynamic_ir_${variant}_direct.json" in story, "story reads current_run from _direct.json")
    check("readCurrentRunDroopMv" in story, "story droop helper is the current_run reader")
    check("goldPresent ? IR_CURRENT_MV" not in story, "story does not invent current_run from the gold file")
    heatmap = (ROOT / "studio/src/components/flowlab/DynamicIrHeatmap.tsx").read_text()
    check("dynamic_ir_${variant}_direct.json" in heatmap, "finish heatmap loads current_run")
    check("dynamic_ir_${variant}.json" not in heatmap, "finish heatmap does not load the gold sentinel")
    dyn_sh = (ROOT / "learn/scripts/run_dynamic_ir.sh").read_text()
    check('JSON="${OUT_DIR}/dynamic_ir_${VARIANT}_direct.json"' in dyn_sh, "dynamic_ir writes current_run _direct.json")
    check('JSON="${OUT_DIR}/dynamic_ir_${VARIANT}.json"' not in dyn_sh, "dynamic_ir does not write the gold sentinel path")
    check("will not write locked gold Dynamic IR" in dyn_sh, "dynamic_ir refuses the gold filename")
    check("dynamic_ir_{variant}_direct.json" in (ROOT / "studio/src/lib/signoff.ts").read_text(), "signoff registry points Dynamic IR at current_run")
    phases = (ROOT / "scripts/test_all_phases.sh").read_text()
    check("dynamic_ir_flowlab_direct.json" in phases, "phase test parses current_run")
    check('r=json.load(open("${ROOT}/learn/sim/reports/dynamic_ir_flowlab.json"))' not in phases, "phase test does not parse gold as current_run")
    check('g.get("gold") is True' in phases, "phase test keeps the gold sentinel")
    studio_api = (ROOT / "scripts/test_studio_api.sh").read_text()
    check("dynamic_ir_flowlab_direct.json" in studio_api, "studio API test parses current_run")
    check('r=json.load(open("${ROOT}/learn/sim/reports/dynamic_ir_flowlab.json"))' not in studio_api, "studio API test does not parse gold as current_run")
    check("45.298" in studio_api, "studio API test keeps the gold sentinel")
    check("_direct.map.csv" in (ROOT / "studio/src/lib/story.ts").read_text(), "story STA IR names the current_run map")
    check("worst_cell_ir_mv" in (ROOT / "studio/src/components/flowlab/StaIrAwarePanel.tsx").read_text(), "STA panel shows worst cell IR")
    finish = (ROOT / "studio/src/components/flowlab/FlowLabSignoff.tsx").read_text()
    check("STA IR-aware overlay (lab" not in finish, "finish does not hide STA IR-aware behind a lab details")
    check('closest("details")' in (ROOT / "studio/src/components/FlowLab.tsx").read_text(), "finish focus opens a parent details")
    check("autonomous goal work" not in (ROOT / "learn/EVIDENCE.md").read_text(), "EVIDENCE is course evidence, not agent diary")
    check("readCurrentRunDroopMv" in story, "story names the current_run droop helper")
    lab_ts = (ROOT / "studio/src/lib/lab.ts").read_text()
    check("readCurrentRunDroopMv" in lab_ts, "lab bench reads current_run from _direct.json")
    check("currentMv: IR_CURRENT_MV" not in lab_ts, "lab bench does not hardcode live IR as 6.075")
    bench = (ROOT / "studio/src/components/LabBench.tsx").read_text()
    check("?? 6.075" not in bench, "LabBench does not invent current_run 6.075")
    check("current_run" in bench, "LabBench labels the live number current_run")
    check("worstCellIrMv" in bench, "LabBench shows STA worst cell IR")
    home = (ROOT / "studio/src/app/page.tsx").read_text()
    check("SuiteHub" not in home, "home does not mount the full hook matrix")
    check("HomeOpsStrip" in home, "home shows toolchain counts only")
    ops = (ROOT / "studio/src/components/HomeOpsStrip.tsx").read_text()
    check("/tools#suite" in ops, "home toolchain strip points at /tools#suite")
    check("suite-hooks" not in ops, "home toolchain strip does not list hooks")
    check("does not launch cooks" in ops, "home toolchain strip does not launch cooks")
    suite_hub = (ROOT / "studio/src/components/SuiteHub.tsx").read_text()
    check("suite-hub-compact" not in suite_hub, "SuiteHub has no compact home dump")
    check("Hooks for course, FlowLab, and product cooks" not in suite_hub, "SuiteHub does not remix the three surfaces as one cook")
    check("own contracts" in suite_hub, "SuiteHub names the surface contracts")
    tools_client = (ROOT / "studio/src/app/tools/tools-client.tsx").read_text()
    check("<SuiteHub" in tools_client, "full hook matrix stays on /tools")
    suite_src = (ROOT / "studio/src/lib/suite.ts").read_text()
    magic = suite_src.split('id: "magic_netgen"')[1].split("},")[0]
    check("apt install magic" not in magic, "Magic/Netgen gap is not an apt close for Nangate LVS")
    check("no FreePDK45" in magic, "Magic/Netgen hook names the missing .tech")
    css = (ROOT / "studio/src/app/globals.css").read_text()
    check("scroll-margin-top" in css and "#suite" in css, "hash targets clear the sticky nav")
    check('href: "/pkg"' in home, "home Package chip goes to /pkg, not FlowLab finish")
    flowlab = (ROOT / "studio/src/components/FlowLab.tsx").read_text()
    check("CLOSE_PHASES" in flowlab, "FlowLab close count excludes PKG")
    check('phases={CLOSE_PHASES}' in flowlab, "FlowLab pipeline omits PKG")
    check('id: "pkg"' not in flowlab, "FlowLab workbench has no PKG phase")
    phases_src = (ROOT / "studio/src/components/flowlab/phases.ts").read_text()
    check('id: "pkg"' not in phases_src, "FlowLab PHASES is RTL → finish only")
    flow_phases = (ROOT / "studio/src/lib/flowlab.ts").read_text().split("export const FLOW_PHASES")[1].split("export type FlowPhaseId")[0]
    check('id: "pkg"' not in flow_phases, "FlowLab status API has no PKG stage")
    check("CLOSE_PHASES.findIndex" in flowlab, "next-phase walk is RTL → finish only")
    check("PHASE_IDS.indexOf(phaseId) + 1" not in flowlab, "next-phase walk does not step onto PKG")
    check("Open PKG" in flowlab, "finish next banner opens /pkg")
    check('router.replace("/pkg")' in flowlab, "stale /flow?phase=pkg opens /pkg")
    check("doneCount / PHASES.length" not in flowlab, "progress ring does not divide by nine phases")
    check('href: "/flow?phase=pkg"' not in home, "home does not treat Package as a FlowLab finish phase")
    vis = (ROOT / "studio/src/components/flowlab/FlowLabPhaseVisual.tsx").read_text()
    check(">Lab viewport<" not in vis, "FlowLab viewport is not labeled Lab")
    check(">FlowLab viewport<" in vis, "phase visual names the FlowLab viewport")
    panel = (ROOT / "studio/src/components/flowlab/SignoffMatrixPanel.tsx").read_text()
    check('href="/flow?phase=pkg"' not in panel, "finish Phase 2 link is /pkg")
    check('href="/pkg"' in panel, "finish Phase 2 stays on /pkg")
    finish_so = (ROOT / "studio/src/components/flowlab/FlowLabSignoff.tsx").read_text()
    check('href="/flow?phase=pkg"' not in finish_so, "finish power strip does not deep-link a FlowLab PKG phase")
    check('href="/pkg"' in finish_so, "finish power strip sends System PDN to /pkg")
    dyn_hook = suite_src.split('id: "dynamic_ir"')[1].split("},")[0]
    check("currentRunDynamicIrPresent" in dyn_hook, "Dynamic IR hook ok is current_run, not gold")
    check("goldDynamicIrPresent()" not in dyn_hook.split("ok:")[1].split("\n")[0], "Dynamic IR hook ok does not call gold")
    check("_direct.json" in dyn_hook, "Dynamic IR hook names current_run _direct.json")
    sys_hook = suite_src.split('id: "system_pdn"')[1].split("},")[0]
    check('href: "/pkg"' in sys_hook, "System PDN hook opens /pkg")
    check("/flow?phase=pkg" not in sys_hook, "System PDN hook is not the FlowLab pkg phase")
    dse_hook = suite_src.split('id: "dse"')[1].split("},")[0]
    check("action:" not in dse_hook, "suite DSE hook has no Tools run action")
    check('href: "/lab"' in dse_hook, "suite DSE hook opens /lab")
    curric = (ROOT / "learn/CURRICULUM.md").read_text()
    post = curric.split("Recommended extensions")[1].split("### Optional")[0]
    check(post.find("Your own RTL") < post.find("sky130hd"), "post-course does not lead with a sky130 switch")
    check("not a PDK switch to close LVS leftover" in post, "post-course names leftover as PDK-gated")
    status = (ROOT / "learn/reference/suite-status.md").read_text()
    dyn_row = next(l for l in status.splitlines() if "| dynamic_ir |" in l and "Power" in l)
    check("_direct.json" in dyn_row, "suite-status dynamic_ir hook is current_run")
    check("gold 45.298 present" not in dyn_row, "suite-status dynamic_ir hook is not the gold sentinel")

    lvs = load("lvs_signoff_flowlab.json")
    check(lvs.get("ok") is True, "LVS compare is a real KLayout match")
    check(int(lvs.get("must_connect") or 0) == 2, "LVS leftover must-connect stays 2")
    msgs = ((lvs.get("artifact_parse") or {}).get("lvsdb") or {}).get("messages") or []
    check(any("DFF_X2" in str(m) for m in msgs), "leftover messages name DFF_X2")
    check(int((lvs.get("leftover") or {}).get("must_connect") or 0) == 2, "LVS leftover object is 2")
    check("DFF_X2" in ((lvs.get("leftover") or {}).get("circuits") or []), "LVS leftover object names DFF_X2")
    check("leftover must-connect 2" in str(lvs.get("summary")), "LVS summary names leftover (not PASS-only)")
    check("with_leftover_summary" in (ROOT / "learn/scripts/run_klayout_lvs.sh").read_text(), "LVS cook stamps leftover into summary")
    require = ROOT / "learn/scripts/signoff_require_ok.py"
    check(require.is_file(), "signoff_require_ok.py exists")
    live_ok = subprocess.run(
        [sys.executable, str(require), str(REPORTS / "lvs_signoff_flowlab.json")],
        capture_output=True,
        text=True,
    )
    check(live_ok.returncode == 0, "leftover-named LVS still exits 0 (compare matches)")
    all_ok = subprocess.run(
        [sys.executable, str(require), str(REPORTS / "signoff_all_flowlab.json")],
        capture_output=True,
        text=True,
    )
    check(all_ok.returncode == 0, "live signoff_all still exits 0")
    with tempfile.TemporaryDirectory() as tmp:
        fail = Path(tmp) / "fail.json"
        fail.write_text(json.dumps({"ok": False, "summary": "LVS FAIL · missing FreePDK45.lylvs"}) + "\n")
        fail_rc = subprocess.run(
            [sys.executable, str(require), str(fail)],
            capture_output=True,
            text=True,
        )
        check(fail_rc.returncode == 1, "failed pillar JSON exits 1")
        check("ok=False" in fail_rc.stdout, "failed pillar names ok=False")
    lvs_sh = (ROOT / "learn/scripts/run_klayout_lvs.sh").read_text()
    check("signoff_require_ok.py" in lvs_sh, "LVS cook fails the shell when ok is not true")
    check("exit 0" not in lvs_sh.split("missing FreePDK45.lylvs")[1].split("fi")[0], "missing lylvs no longer exits 0")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_sta_signoff.sh").read_text(), "STA cook fails the shell when ok is not true")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_drc_signoff.sh").read_text(), "DRC cook fails the shell when ok is not true")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_power_signoff.sh").read_text(), "power cook fails the shell when ok is not true")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_chip_pdn_ir.sh").read_text(), "chip IR cook fails the shell when ok is not true")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_system_pdn.sh").read_text(), "system PDN cook fails the shell when ok is not true")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_vyges_em_ir.sh").read_text(), "vyges cook fails the shell when ok is not true")
    chip_ir = load("pdn_chip_ir_flowlab.json")
    check(chip_ir.get("ok") is True, "live chip IR report has ok")
    chip_hook = suite_src.split('id: "chip_pdn_ir"')[1].split("},")[0]
    check("signoffReportPass" in chip_hook, "suite chip IR ok is the JSON report, not the stamp")
    check('href: "/flow?phase=finish#ir"' in chip_hook, "suite chip IR opens the finish IR ledger")
    vy_hook = suite_src.split('id: "vyges_em_ir"')[1].split("},")[0]
    check('href: "/flow?phase=finish#ir"' in vy_hook, "suite vyges opens the finish IR ledger")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_signoff_all.sh").read_text(), "signoff_all re-reads stamped JSON ok")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_pkg_signoff.sh").read_text(), "pkg_signoff fails the shell when ok is not true")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_pkg_bump.sh").read_text(), "pkg_bump fails the shell when ok is not true")
    check("signoff_require_ok.py" in (ROOT / "learn/scripts/run_signoff_phase2.sh").read_text(), "signoff_phase2 re-reads stamped JSON ok")
    pwr_sh = (ROOT / "learn/scripts/run_power_signoff.sh").read_text()
    check('learn/scripts/run_system_pdn.sh' not in pwr_sh, "power_signoff does not cook System PDN")
    check('"system_pdn"' not in pwr_sh, "power_signoff steps are chip-only")
    pkg_sh = (ROOT / "learn/scripts/run_pkg_signoff.sh").read_text()
    check("run_system_pdn.sh" in pkg_sh, "pkg_signoff cooks System PDN")
    check("if sys_ok is None" not in pkg_sh, "pkg_signoff does not treat a summary as ok")
    check("system_droop_mv_max" in pkg_sh, "pkg_signoff gates system droop against golden")
    hier = (ROOT / "learn/scripts/system_pdn_hier.py").read_text()
    check('report["ok"]' in hier, "system PDN JSON writes ok")
    sig_ts = (ROOT / "studio/src/lib/signoff.ts").read_text()
    power_checks = sig_ts.split('id: "power"')[1].split("SIGNOFF_PLANNED_PILLARS")[0]
    pkg_checks = sig_ts.split('id: "pkg"')[1].split('id: "thermal"')[0]
    check('id: "system_pdn"' not in power_checks, "power pillar checks do not include System PDN")
    check('id: "system_pdn"' in pkg_checks, "PKG pillar checks include System PDN")
    check("signoffReportPass" in sys_hook, "suite System PDN ok reads JSON, not only the stamp")
    ph2_ok = subprocess.run(
        [sys.executable, str(require), str(REPORTS / "signoff_phase2_flowlab.json")],
        capture_output=True,
        text=True,
    )
    check(ph2_ok.returncode == 0, "live signoff_phase2 still exits 0")
    pkg_ok = subprocess.run(
        [sys.executable, str(require), str(REPORTS / "pkg_signoff_flowlab.json")],
        capture_output=True,
        text=True,
    )
    check(pkg_ok.returncode == 0, "live pkg_signoff still exits 0")
    check("RTL→PKG chain" not in (ROOT / "learn/reference/README.md").read_text(), "reference index does not title the chain RTL→PKG")
    check("RTL→PKG phase linkage" not in (ROOT / "learn/sim/spice/README.md").read_text(), "spice README does not call the chain RTL→PKG")
    check("full RTL→PKG flow" not in (ROOT / "learn/reference/spice-ngspice-primer.md").read_text(), "ngspice primer does not call the close RTL→PKG")
    check("with_leftover_summary" in (ROOT / "learn/scripts/stamp_signoff_all.py").read_text(), "stamp writes leftover into LVS summary")
    panel = (ROOT / "studio/src/components/flowlab/SignoffMatrixPanel.tsx").read_text()
    check('{data.evaluation.ok ? "PASS"' not in panel, "signoff matrix does not print a bare PASS")
    check("Four pillars ok" in panel, "signoff matrix global line names four pillars")
    check("Four-pillar close" in panel, "finish global line is the four-pillar close")
    check("Phase 2 (after signoff)" in panel, "Phase 2 is after signoff, not in the four-pillar ok")
    check("signoff_all" in panel, "signoff matrix global line uses the signoff_all summary")
    signoff_ts = (ROOT / "studio/src/lib/signoff.ts").read_text()
    check("closeGates" in signoff_ts and "closeGates.every" in signoff_ts, "evaluateSignoffGates ok is four pillars")
    ok_line = next(l for l in signoff_ts.splitlines() if "closeGates.every" in l)
    check("PLANNED" not in ok_line, "four-pillar ok does not fold pkg/thermal")
    check("allReport?.ok === true" in ok_line, "four-pillar ok requires the signoff_all stamp")
    check("!== false" not in ok_line, "missing signoff_all is not treated as ok")
    check("phase2Ok" in signoff_ts, "Phase 2 has its own ok bit")
    check("ready: gates.ok" in story, "home signoff step requires evaluateSignoffGates ok")
    check("signoffPassed === pillars.length" not in story, "home signoff ready is not pillar-count-only")
    flow_page = (ROOT / "studio/src/app/flow/page.tsx").read_text()
    check('redirect("/pkg")' in flow_page, "server /flow?phase=pkg redirects to /pkg")
    check("!reports/dynamic_ir_flowlab_direct.json" in (ROOT / "learn/sim/.gitignore").read_text(), "current_run IR report is not gitignored")
    check("!reports/vyges_em_ir_flowlab.json" in (ROOT / "learn/sim/.gitignore").read_text(), "vyges EM report is not gitignored")
    check("Signoff · leftover named" in story, "home story labels leftover on the signoff step")
    check("Gold ${IR_GOLD_MV} mV (reference_run)" not in story, "story IR does not lead with gold as the live number")
    check("current_run ${liveMv" in story, "story IR leads with current_run")
    check("After signoff" in home, "home PKG chip is after signoff")
    check("0 GAP" not in (ROOT / "docs/results.md").read_text(), "results.md does not claim 0 GAP")
    curric = (ROOT / "learn/CURRICULUM.md").read_text()
    check("A gold + B SA-AMG" not in curric, "curriculum Dynamic IR is current_run, not A gold")
    check("| Thermal | no tool in VM |" not in curric, "curriculum thermal is HotSpot, not missing")
    evidence = (ROOT / "learn/EVIDENCE.md").read_text()
    check("leftover must-connect 2 (DFF_X2)" in evidence, "EVIDENCE names LVS leftover")
    check("Phase 1 complete" not in evidence, "EVIDENCE does not call Phase 1 complete")
    dyn_md = (ROOT / "learn/reference/dynamic-ir.md").read_text()
    check("Solver A gold + Solver B" not in dyn_md.splitlines()[0], "dynamic-ir title is current_run, not gold")
    check("_direct.json" in dyn_md, "dynamic-ir names current_run _direct.json")
    tail = ((lvs.get("artifact_parse") or {}).get("log") or {}).get("tail") or []
    check(any("CONGRATULATIONS" in str(x) or "Netlists match" in str(x) for x in tail), "LVS log keeps the match line")
    check(not any("Netlists don't match" in str(x) for x in tail), "LVS log has no mismatch line")
    stamp = ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/.lvs.ok"
    check(stamp.exists(), "matched LVS stamps .lvs.ok")

    rdl = load("pkg_rdl_flowlab.json")
    check(rdl.get("ok") is True, "pkg_rdl executed dummy rdl_route")
    check(rdl.get("status") == "READY", "pkg_rdl status is READY")
    check((rdl.get("rdl") or {}).get("executed") is True, "rdl_route wrote sidecar wires")
    check((rdl.get("evaluation") or {}).get("ok") is True, "pkg_rdl evaluation.ok is true")
    note = str(rdl.get("educational_note") or "")
    check("not C4" in note or "dummy" in note.lower(), "pkg_rdl keeps dummy-not-C4 label")

    bump = load("pkg_bump_flowlab.json")
    check(bump.get("ok") is True, "pkg_bump executed on mesh+config")

    pkg = load("pkg_signoff_flowlab.json")
    check(pkg.get("ok") is True, "pkg_signoff ok from bump + system PDN")
    rdl_step = (pkg.get("steps") or {}).get("pkg_rdl") or {}
    check(rdl_step.get("ok") is True, "pkg_signoff records dummy rdl_route ok")
    rdl_check = next(
        (c for c in (pkg.get("evaluation") or {}).get("checks") or [] if c.get("id") == "pkg_rdl"),
        None,
    )
    check(rdl_check is not None and rdl_check.get("ok") is True, "nested RDL check is pass")

    ph2 = load("signoff_phase2_flowlab.json")
    check(ph2.get("ok") is True, "phase 2 ok from HotSpot + executable PKG")
    check((ph2.get("pillars") or {}).get("thermal", {}).get("ok") is True, "HotSpot thermal ok")
    thermal = load("thermal_signoff_flowlab.json")
    check(thermal.get("ok") is True, "thermal_signoff ok")
    tmax = (thermal.get("thermal") or {}).get("t_max_c")
    check(tmax is not None and float(tmax) < 85.0, f"HotSpot t_max_c={tmax} under 85")
    check((thermal.get("thermal") or {}).get("engine") == "hotspot", "thermal engine is hotspot")

    sta_ir = load("sta_ir_aware_flowlab.json")
    check(sta_ir.get("ok") is True, "STA IR-aware report ok")
    sta_map = str((sta_ir.get("ir") or {}).get("map") or "")
    check(sta_map.endswith("dynamic_ir_flowlab_direct.map.csv"), "STA IR-aware uses current_run map")
    check("dynamic_ir_flowlab.map.csv" not in sta_map.replace("_direct.map.csv", ""), "STA IR-aware map is not the gold sentinel")
    check(abs(float((sta_ir.get("ir") or {}).get("worst_cell_ir_mv") or 0) - 6.075) < 0.02, "STA IR-aware worst cell is current_run 6.075 mV")
    sta_sh = (ROOT / "learn/scripts/run_sta_ir_aware.sh").read_text()
    check('MAP="${OUT_DIR}/dynamic_ir_${VARIANT}_direct.map.csv"' in sta_sh, "STA IR-aware wrapper pins current_run map")
    check('dynamic_ir_${VARIANT}.map.csv' not in sta_sh, "STA IR-aware wrapper does not fall back to gold map")
    check("will not scale STA from locked gold Dynamic IR map" in sta_sh, "STA IR-aware wrapper refuses the gold map name")
    sta_py = (ROOT / "learn/scripts/sta_ir_aware.py").read_text()
    check("refuse_gold_map" in sta_py, "STA IR-aware Python refuses the gold map")
    check("dynamic_ir_flowlab.map.csv" in sta_py, "STA IR-aware names the gold map sentinel")

    signoff_all = load("signoff_all_flowlab.json")
    check(signoff_all.get("ok") is True, "signoff_all follows the four pillars")
    pillars = signoff_all.get("pillars") or {}
    check(all(pillars.get(k, {}).get("ok") for k in ("timing", "geometry", "equivalence", "power")), "four signoff pillars ok")
    leftover = signoff_all.get("leftover") or {}
    check(int(leftover.get("must_connect") or 0) == 2, "signoff_all leftover must-connect is 2")
    check("DFF_X2" in (leftover.get("circuits") or []), "signoff_all leftover names DFF_X2")
    check("leftover must-connect 2" in str(signoff_all.get("summary")), "signoff_all summary names leftover")
    matrix = (ROOT / "learn/reference/signoff-matrix.md").read_text()
    check("leftover must-connect 2 on DFF_X2" in matrix, "signoff-matrix names leftover")
    check("dynamic_ir_{v}_direct.map.csv" in matrix, "signoff-matrix pins STA IR-aware to current_run map")
    check("LVS clean (educational)" not in matrix, "signoff-matrix does not call LVS clean")
    check("/flow?phase=finish" in matrix, "signoff-matrix points the matrix at finish")
    check("System PDN + Phase 2" in matrix, "signoff-matrix names PKG as System PDN + Phase 2")
    check("Full matrix + power chain" not in matrix, "signoff-matrix does not claim PKG hosts the full matrix")
    check("FlowLab finish/PKG" not in matrix, "signoff-matrix DoD does not still say finish/PKG")
    suite = (ROOT / "studio/src/lib/suite.ts").read_text()
    pwr_href = suite.split('id: "power_signoff"')[1].split("},")[0]
    all_href = suite.split('id: "signoff_all"')[1].split("},")[0]
    check("/flow?phase=finish#ir" in pwr_href, "suite power_signoff points at finish IR")
    check("/flow?phase=finish#signoff" in all_href, "suite signoff_all points at finish")
    check('href: "/pkg"' not in pwr_href, "suite power_signoff is not on /pkg")
    check('href: "/pkg"' not in all_href, "suite signoff_all is not on /pkg")
    check("Power / PKG" not in (ROOT / "studio/src/lib/signoff.ts").read_text(), "power pillar is not labeled Power / PKG")
    check("Power / PKG" not in (ROOT / "learn/lessons/07-finish/README.md").read_text(), "lesson 07 does not call the power pillar PKG")
    check("Power / PKG" not in matrix, "signoff-matrix does not call the power pillar PKG")
    check("power/PKG" not in matrix, "signoff-matrix intro does not merge power with PKG")
    check("dynamic_ir_{v}_direct.json" in matrix, "signoff-matrix names current_run Dynamic IR")
    check("| Dynamic IR I(t) | `dynamic_ir` | `dynamic_ir_{v}.json`" not in matrix, "signoff-matrix does not list gold as the Dynamic IR cook")
    check("currentRunDynamicIrPresent" in suite, "suite Dynamic IR status reads _direct.json")
    check("ok: goldDynamicIrPresent()" not in suite, "suite Dynamic IR ok is not the gold sentinel")
    status = (ROOT / "learn/reference/suite-status.md").read_text()
    check("gold 45.298 LOCKED counts as present" not in status, "suite-status does not treat gold as the Dynamic IR cook")
    check("from `_direct.json`" in status, "suite-status names current_run for the Dynamic IR hook")
    chain = (ROOT / "learn/reference/spice-power-chain.md").read_text()
    check("](/pkg)" in chain, "spice-power-chain names the PKG hub")
    check("RTL → PKG power chain" not in chain, "spice-power-chain title is not RTL → PKG")
    check("9 FlowLab phases" not in chain, "spice-power-chain is eight close phases, not nine")
    lvs_hook = suite.split('id: "lvs_signoff"')[1].split("},")[0]
    check("leftover must-connect 2" in lvs_hook, "suite LVS hook names leftover")
    vyges_hook = suite.split('id: "vyges_em_ir"')[1].split("},")[0]
    check("vygesEmHookDetail" in vyges_hook, "suite vyges hook reads em_checked from the report")
    check("em_checked" in (ROOT / "studio/src/lib/signoff.ts").read_text().split('check.id === "vyges_em_ir"')[1].split("return")[0], "signoff matrix names em_checked on the vyges check")
    check("CG + backward Euler on PDNSim mesh" not in vyges_hook, "suite vyges hook does not hide em_checked")
    vyges = load("vyges_em_ir_flowlab.json")
    check(vyges.get("ok") is True, "vyges ok means the engine ran")
    check(vyges.get("limits_met") is False, "vyges limits_met is false without emlimit")
    check("em_checked 0" in str(vyges.get("summary")), "vyges summary names em_checked 0")
    check("ir_met false" in str(vyges.get("summary")), "vyges summary names ir_met false")
    sys_rep = load("system_pdn_flowlab.json")
    check(sys_rep.get("ok") is True, "live system PDN report has ok")
    check("em_checked {em_checked}" in (ROOT / "learn/scripts/run_vyges_em_ir.sh").read_text(), "vyges cook stamps em_checked into summary")
    check("A gold + B SA-AMG" not in str((current.get("roles") or {}).get("this_engine")), "current_run this_engine is not A gold")
    check("current_run" in str((current.get("roles") or {}).get("this_engine")), "current_run this_engine names current_run")
    check("A gold + B SA-AMG" not in (ROOT / "learn/scripts/pdn_dynamic.py").read_text(), "pdn_dynamic no longer stamps A gold as this_engine")
    therm = suite.split('id: "thermal_signoff"')[1].split("},")[0]
    check("thermalHookDetail" in therm, "Thermal hook reads t_max from the HotSpot report")
    check("HotSpot t_max °C" not in therm, "Thermal hook does not print a blank t_max")
    check('"label": "LVS clean"' not in (ROOT / "learn/scripts/signoff_eval.py").read_text(), "evaluator does not label LVS as clean")
    check('"label": "LVS clean"' not in (REPORTS / "lvs_signoff_flowlab.json").read_text(), "flowlab LVS report does not say LVS clean")
    check("KLayout match" in (REPORTS / "lvs_signoff_flowlab.json").read_text(), "flowlab LVS report names the compare")
    lab07 = (ROOT / "learn/lessons/07-finish/LAB.md").read_text()
    check("/pkg" not in lab07.split("Part 7")[1] if "Part 7" in lab07 else True, "LAB 07 signoff is on finish, not PKG")
    check("foundry contract" not in lab07.lower() and "enterprise signoff" not in lab07.lower(), "LAB 07 signoff is educational")
    gaps_eval = (ROOT / "learn/reference/remaining-gaps-evaluation.md").read_text()
    check("Closed on FlowLab GCD compare" in gaps_eval, "LVS feasibility is closed")
    check("LVS is clean" not in gaps_eval, "gaps eval does not call sky130 LVS clean")
    eq = pillars.get("equivalence") or {}
    check(int((eq.get("leftover") or {}).get("must_connect") or 0) == 2, "equivalence pillar carries leftover")
    ledger_all = signoff_all.get("ir_mesh_ledger") or {}
    check(ledger_all.get("comparable") is False, "signoff_all IR ledger not comparable")
    check(int(ledger_all.get("n_meshes") or 0) >= 5, "signoff_all ledger has five meshes")
    check("stamp_signoff_all.py" in (ROOT / "learn/scripts/run_signoff_all.sh").read_text(), "signoff_all restamps leftover from pillar reports")
    check("leftover_from_lvs" in (ROOT / "learn/scripts/run_klayout_lvs.sh").read_text(), "LVS signoff writes leftover object")
    from stamp_signoff_all import leftover_from_lvs, build, with_leftover_summary
    parsed = leftover_from_lvs(lvs)
    check(parsed is not None and parsed["must_connect"] == 2, "stamp leftover_from_lvs reads LVS")
    check("DFF_X2" in parsed["circuits"], "stamp leftover_from_lvs names DFF_X2")
    check(
        with_leftover_summary("LVS PASS · errors 0", parsed) == "LVS PASS · errors 0 · leftover must-connect 2 (DFF_X2)",
        "with_leftover_summary appends leftover once",
    )
    check(
        with_leftover_summary("LVS PASS · errors 0 · leftover must-connect 2 (DFF_X2)", parsed)
        == "LVS PASS · errors 0 · leftover must-connect 2 (DFF_X2)",
        "with_leftover_summary does not double-append",
    )
    rebuilt = build("flowlab")
    check(rebuilt.get("ok") is True, "stamp rebuild is ok")
    check(int((rebuilt.get("leftover") or {}).get("must_connect") or 0) == 2, "stamp rebuild leftover")
    pwr = load("power_signoff_flowlab.json")
    ledger = pwr.get("ir_mesh_ledger") or {}
    check(ledger.get("comparable") is False, "power_signoff IR meshes are not comparable")
    ids = {m.get("id") for m in (ledger.get("meshes") or [])}
    check({"gold_dynamic_ir", "chip_pdn", "vyges_em_ir"} <= ids, "ledger names gold, chip, and vyges")
    lesson07 = (ROOT / "learn/lessons/07-finish/README.md").read_text()
    check("0–5.2 mV" not in lesson07 and "0-5.2 mV" not in lesson07, "lesson 07 does not quote a single 0–5.2 mV IR")
    check("comparable: false" in lesson07 and "45.298" in lesson07, "lesson 07 names IR meshes not interchangeable")
    golden = (ROOT / "learn/reference/golden-metrics.md").read_text()
    check("0–5.2 mV" not in golden, "golden-metrics does not treat the ORFS PNG as the IR number")
    check("not gold" in golden and "45.298" in golden, "golden-metrics points IR at the ledger")

    gate = load("gate_sim_flowlab.json")
    check(gate.get("ok") is True, "gate_sim report ok")
    check(gate.get("status") == "READY", "gate_sim READY")

    vl = load("vectorless_flowlab.json")
    check(vl.get("ok") is True, "vectorless report ok")
    dyn_src = str((vl.get("dynamic") or {}).get("source") or "")
    check("gcd_gate.vcd" in dyn_src, "dynamic source is gate VCD")
    check("tb_gcd_gate/dut" in dyn_src, "dynamic VCD scope is tb_gcd_gate/dut")

    gc = load("gridcheck_flowlab.json")
    check(gc.get("ok") is True, "gridcheck flowlab ok")
    check(gc.get("vdd_connected") is True and gc.get("vss_connected") is True, "gridcheck VDD+VSS")

    spice = load("spice_engines_flowlab.json")
    check(spice.get("xyce_status") == "READY", "Xyce N4 READY in spice_engines")
    check((spice.get("xyce_n4") or {}).get("ok") is True, "Xyce N4 gold ok")

    pex = load("analytical_pex_flowlab.json")
    check(pex.get("ok") is True, "analytical_pex ok")
    fc = pex.get("fastercap") or {}
    check(fc.get("status") == "READY", "FasterCap BEM READY")
    check(float(fc.get("c_couple_fF") or 0) > 0, "FasterCap Cc > 0")

    ccs = load("ccs_char_flowlab.json")
    check(ccs.get("ok") is True, "ccs_char report ok")
    check(ccs.get("status") == "READY", "ccs_char READY")
    check((ccs.get("official_probe") or {}).get("status") == "GAP", "official Nangate liberty stays NLDM GAP")
    check((ccs.get("official_probe") or {}).get("n_ccs_tables", 1) == 0, "official lib has zero CCS tables")
    check(int(ccs.get("n_ccs_tables") or 0) >= 30, "sidecar has ≥15 cells × rise/fall")
    check(int(ccs.get("n_cells") or 0) >= 15, "at least 15 GCD combo cells characterized")
    check("INV_X1" in (ccs.get("cells") or []), "INV_X1 still in sidecar")
    check("AOI21_X1" in (ccs.get("cells") or []), "AOI21_X1 in sidecar")
    check("CLKBUF_X1" in (ccs.get("cells") or []), "CLKBUF_X1 in sidecar")
    check(0.25 <= float(ccs.get("delay_ratio_vs_nldm") or 0) <= 4.0, "PTM delay within band of NLDM")
    sidecar = ROOT / "learn/sim/lib/nangate45_ptm_ccs_sidecar.lib"
    inv = ROOT / "learn/sim/lib/INV_X1_ptm45_ccs.lib"
    check(sidecar.is_file(), "multi-cell sidecar CCS liberty exists")
    check(inv.is_file(), "INV_X1 sidecar still exists")
    check("output_current_fall" in sidecar.read_text(), "sidecar contains output_current_fall")
    check("cell (NAND2_X1)" in sidecar.read_text(), "sidecar includes NAND2_X1")

    deep = load("lvs_deep_flowlab.json")
    check(deep.get("ok") is True, "deep transistor LVS matches")
    check((deep.get("transistor") or {}).get("ok") is True, "transistor compare is match")
    check(int(deep.get("n_filtered_masters") or 0) >= 30, "filtered CDL keeps used masters")
    check(int((deep.get("transistor") or {}).get("n_flatten", 99)) == 0, "unused library flatten is gone")
    check(deep.get("well_to_rails") is True, "deep LVS maps wells to VDD/VSS")
    check(deep.get("fill_from_def") is True, "deep LVS injects FILL from DEF")
    check((ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/.lvs.ok").exists(), "transistor match may stamp .lvs.ok")
    print("ALL test_signoff_honesty PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import fs from "fs";
import path from "path";
import { execFileSync } from "child_process";
import { LEARN_ROOT, REPO_ROOT, LESSONS, readProgress } from "./course";
import { resultsDir, detectDisplay, listOpenTargets } from "./open";
import { viewerStatus } from "./webviewer";
import { listJobs, readLock, getPipelineStatus } from "./jobs";
import { probeToolchain } from "./run";

export type HookStatus = {
  id: string;
  label: string;
  group: string;
  ok: boolean;
  detail: string;
  action?: string;
  href?: string;
};

function has(rel: string) {
  return fs.existsSync(path.join(resultsDir(), rel));
}

function which(bin: string) {
  try {
    execFileSync("which", [bin], { encoding: "utf8" });
    return true;
  } catch {
    return false;
  }
}

function signoffReportOk(variant: string, name: string) {
  return fs.existsSync(path.join(LEARN_ROOT, "sim/reports", `${name}_${variant}.json`));
}

function signoffReportPass(variant: string, name: string) {
  const p = path.join(LEARN_ROOT, "sim/reports", `${name}_${variant}.json`);
  if (!fs.existsSync(p)) return false;
  try {
    const j = JSON.parse(fs.readFileSync(p, "utf8")) as { ok?: boolean };
    return j.ok === true;
  } catch {
    return false;
  }
}

function powerReportOk(variant: string, name: string) {
  return fs.existsSync(path.join(LEARN_ROOT, "sim/reports", `${name}_${variant}.log`));
}

function powerChainOk() {
  for (const v of ["flowlab", "learn"]) {
    const log = path.join(LEARN_ROOT, `sim/reports/power_chain_${v}.log`);
    if (fs.existsSync(log)) {
      try {
        const text = fs.readFileSync(log, "utf8");
        if (text.includes("POWER_CHAIN_DONE")) return true;
      } catch {
        /* ignore */
      }
    }
  }
  return false;
}

export async function getSuiteStatus() {
  const tools = await probeToolchain();
  const display = detectDisplay();
  const viewer = viewerStatus();
  const lock = readLock();
  const jobs = listJobs(5);
  const pipeline = getPipelineStatus();
  const progress = readProgress();
  const open = listOpenTargets();

  const hooks: HookStatus[] = [
    {
      id: "toolchain",
      label: "Toolchain core",
      group: "Ambiente",
      ok: tools.tools.filter((t) => ["openroad", "yosys", "sta", "klayout"].includes(t.name)).every((t) => t.ok) && tools.orfs,
      detail: tools.tools.map((t) => `${t.name}:${t.ok ? "ok" : "no"}`).join(" · "),
      href: "/tools",
    },
    {
      id: "magic_netgen",
      label: "Magic / Netgen",
      group: "Ambiente",
      ok: which("magic") && (which("netgen") || which("netgen-lvs")),
      detail: which("magic")
        ? "present · LVS Nangate resta KLayout (no FreePDK45 .tech)"
        : "apt install magic netgen-lvs",
      action: "layout_tools",
    },
    {
      id: "ngspice",
      label: "ngspice (System PDN)",
      group: "Ambiente",
      ok: which("ngspice"),
      detail: which("ngspice") ? "ngspice present · Xyce GAP" : "apt install ngspice",
      action: "system_pdn",
    },
    {
      id: "iverilog",
      label: "Icarus (RTL sim)",
      group: "Ambiente",
      ok: which("iverilog"),
      detail: which("iverilog") ? "iverilog present" : "install iverilog",
      action: "rtl_sim",
    },
    {
      id: "display",
      label: "DISPLAY / Desktop",
      group: "Ambiente",
      ok: Boolean(display),
      detail: display ? `DISPLAY ${display}` : "open Desktop on cursor.com/agents",
    },
    {
      id: "rtl",
      label: "RTL GCD",
      group: "Frontend",
      ok: fs.existsSync(
        path.join(REPO_ROOT, "tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v"),
      ),
      detail: "designs/src/gcd/gcd.v",
      action: "rtl_sim",
    },
    {
      id: "rtl_sim",
      label: "RTL sim + VCD",
      group: "Frontend",
      ok: which("iverilog") && fs.existsSync(path.join(LEARN_ROOT, "sim/gcd/tb_gcd.v")),
      detail: "run_rtl_sim.sh · rtl_sim action",
      action: "rtl_sim",
      href: "/tools?tab=run&action=rtl_sim",
    },
    {
      id: "synth",
      label: "Synthesis / ODB synth",
      group: "PD",
      ok: has("1_synth.odb"),
      detail: has("1_synth.odb") ? "1_synth.odb ok" : "run synth",
      action: "synth",
      href: "/tools?stage=synth&tab=results",
    },
    {
      id: "pdn",
      label: "PDN",
      group: "PD",
      ok: has("2_4_floorplan_pdn.odb"),
      detail: has("2_4_floorplan_pdn.odb") ? "2_4_floorplan_pdn.odb" : "run floorplan",
      href: "/tools?stage=floorplan&tab=results",
    },
    {
      id: "gridcheck",
      label: "Gridcheck",
      group: "Power",
      ok:
        fs.existsSync(path.join(resultsDir("flowlab"), ".gridcheck_pdn.ok")) ||
        fs.existsSync(path.join(resultsDir("learn"), ".gridcheck_pdn.ok")) ||
        has("2_4_floorplan_pdn.odb"),
      detail: "check_power_grid · gridcheck action / PDN phase",
      action: "gridcheck",
      href: "/flow?phase=pdn",
    },
    {
      id: "system_pdn",
      label: "System PDN",
      group: "Power",
      ok:
        fs.existsSync(path.join(resultsDir("flowlab"), ".system_pdn.ok")) ||
        fs.existsSync(path.join(resultsDir("learn"), ".system_pdn.ok")),
      detail: "ngspice VRM→board→pkg→die · Z(f)+load-step · PKG phase",
      action: "system_pdn",
      href: "/flow?phase=pkg",
    },
    {
      id: "finish",
      label: "Finish GDS/SPEF",
      group: "PD",
      ok: has("6_final.gds") && has("6_final.odb"),
      detail: has("6_final.gds") ? "6_final.* present" : "run finish",
      action: "finish",
      href: "/tools?stage=finish&tab=results",
    },
    {
      id: "activity",
      label: "Activity → power",
      group: "Power",
      ok:
        powerReportOk("flowlab", "activity_power") ||
        powerReportOk("learn", "activity_power"),
      detail: "VCD se rtl_sim · report_power → I_avg System PDN",
      action: "activity_power",
      href: "/tools?tab=run&action=activity_power",
    },
    {
      id: "vectorless",
      label: "Vectorless / dynamic IR",
      group: "Power",
      ok:
        signoffReportPass("flowlab", "vectorless") ||
        signoffReportPass("learn", "vectorless"),
      detail: "Najm P01 + Kouroussis envelope · VCD vs global 0.5",
      action: "vectorless",
      href: "/tools?tab=run&action=vectorless",
    },
    {
      id: "chip_pdn_ir",
      label: "Chip IR mesh",
      group: "Power",
      ok:
        fs.existsSync(path.join(resultsDir("flowlab"), ".chip_pdn_ir.ok")) ||
        fs.existsSync(path.join(resultsDir("learn"), ".chip_pdn_ir.ok")),
      detail: "write_pg_spice · pdn_transient",
      action: "chip_pdn_ir",
      href: "/tools?tab=run&action=chip_pdn_ir",
    },
    {
      id: "vyges_em_ir",
      label: "vyges-em-ir",
      group: "Power",
      ok:
        signoffReportPass("flowlab", "vyges_em_ir") ||
        signoffReportPass("learn", "vyges_em_ir"),
      detail: "Apache-2.0 binary · CG + backward Euler on PDNSim mesh",
      action: "vyges_em_ir",
      href: "/tools?tab=run&action=vyges_em_ir",
    },
    {
      id: "dynamic_ir",
      label: "Dynamic IR I(t)",
      group: "Power",
      ok:
        signoffReportPass("flowlab", "dynamic_ir") ||
        signoffReportPass("learn", "dynamic_ir"),
      detail: "A DirectLU current_run + B SA-AMG · not reference_run 45.298",
      action: "dynamic_ir",
      href: "/tools?tab=run&action=dynamic_ir",
    },
    {
      id: "dse",
      label: "DSE fisico-aware",
      group: "Power",
      ok:
        signoffReportPass("flowlab", "dse") || signoffReportPass("learn", "dse"),
      detail: "E-graph dpath + BOiLS SSK-GP + IR F4 oracle · Pareto by level",
      action: "dse",
      href: "/tools?tab=run&action=dse",
    },
    {
      id: "power_chain",
      label: "SPICE chain",
      group: "Power",
      ok: powerChainOk(),
      detail: "activity → chip IR → system → export",
      action: "power_chain",
      href: "/tools?tab=run&action=power_chain",
    },
    {
      id: "spice_lab",
      label: "SPICE lab export",
      group: "Power",
      ok: fs.existsSync(path.join(LEARN_ROOT, "sim/spice/INDEX_flowlab.md")),
      detail: "export_spice_lab · mesh_stats + netlist",
      action: "export_spice_lab",
      href: "/tools?tab=run&action=export_spice_lab",
    },
    {
      id: "klayout_drc",
      label: "KLayout DRC",
      group: "Signoff",
      ok: has("6_final.gds"),
      detail: "run_klayout_drc.sh",
      action: "klayout_drc",
      href: "/tools?tab=run&action=klayout_drc",
    },
    {
      id: "sta_signoff",
      label: "STA signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "sta_signoff") || signoffReportPass("learn", "sta_signoff"),
      detail: "WNS/TNS vs golden-gcd · run_sta_signoff.sh",
      action: "sta_signoff",
      href: "/flow?phase=finish",
    },
    {
      id: "drc_signoff",
      label: "DRC signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "drc_signoff") || signoffReportPass("learn", "drc_signoff"),
      detail: "Route DRC + KLayout GDS · run_drc_signoff.sh",
      action: "drc_signoff",
      href: "/flow?phase=finish",
    },
    {
      id: "lvs_signoff",
      label: "LVS signoff",
      group: "Signoff",
      ok:
        signoffReportOk("flowlab", "lvs_signoff") ||
        signoffReportOk("learn", "lvs_signoff") ||
        fs.existsSync(path.join(resultsDir("flowlab"), ".lvs.ok")),
      detail: "ORFS make lvs · educational PASS optional",
      action: "klayout_lvs",
      href: "/flow?phase=finish",
    },
    {
      id: "power_signoff",
      label: "Power signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "power_signoff") || signoffReportPass("learn", "power_signoff"),
      detail: "Power chain + golden gate",
      action: "power_signoff",
      href: "/pkg",
    },
    {
      id: "signoff_all",
      label: "Full signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "signoff_all") || signoffReportPass("learn", "signoff_all"),
      detail: "STA → DRC → LVS → power",
      action: "signoff_all",
      href: "/pkg",
    },
    {
      id: "thermal_signoff",
      label: "Thermal proxy",
      group: "Signoff",
      ok: signoffReportOk("flowlab", "thermal_signoff") || signoffReportOk("learn", "thermal_signoff"),
      detail: "IR+droop proxy · run_thermal_signoff.sh",
      action: "thermal_signoff",
      href: "/pkg",
    },
    {
      id: "pkg_signoff",
      label: "PKG signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "pkg_signoff") || signoffReportPass("learn", "pkg_signoff"),
      detail: "Bump + RDL edu + system PDN",
      action: "pkg_signoff",
      href: "/pkg",
    },
    {
      id: "signoff_phase2",
      label: "Signoff Phase 2",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "signoff_phase2") || signoffReportPass("learn", "signoff_phase2"),
      detail: "Thermal proxy + PKG orchestrator",
      action: "signoff_phase2",
      href: "/pkg",
    },
    {
      id: "or-web",
      label: "OpenROAD Web Viewer",
      group: "GUI",
      ok: true,
      detail: viewer.running ? `live ${viewer.url}` : "POST /api/viewer",
      href: "/tools?stage=cts&tab=results#inspect",
    },
    {
      id: "or-gui",
      label: "OpenROAD Qt GUI",
      group: "GUI",
      ok: Boolean(display) && open.targets.some((t) => t.kind === "openroad" && t.exists),
      detail: "POST /api/open · Ctrl+K",
    },
    {
      id: "yosys_equiv",
      label: "Yosys equiv (EQY-class)",
      group: "Analisi",
      ok:
        signoffReportPass("flowlab", "yosys_equiv") ||
        signoffReportPass("learn", "yosys_equiv"),
      detail: "RTL ↔ generic synth · equiv_induct",
      action: "yosys_equiv",
      href: "/tools?tab=run&action=yosys_equiv",
    },
    {
      id: "formal_gcd",
      label: "Formal SAT (sby-class)",
      group: "Analisi",
      ok:
        signoffReportPass("flowlab", "formal_gcd") ||
        signoffReportPass("learn", "formal_gcd"),
      detail: "reset |-> !resp_val · yosys sat tempinduct",
      action: "formal_gcd",
      href: "/tools?tab=run&action=formal_gcd",
    },
    {
      id: "openrcx",
      label: "OpenRCX SPEF",
      group: "Analisi",
      ok:
        signoffReportPass("flowlab", "openrcx") ||
        signoffReportPass("learn", "openrcx"),
      detail: "StarRC-class extract · 6_final.spef",
      action: "openrcx_report",
      href: "/tools?tab=run&action=openrcx_report",
    },
    {
      id: "analytical_pex",
      label: "PEX analitico (FasterCap-class)",
      group: "Analisi",
      ok:
        signoffReportPass("flowlab", "analytical_pex") ||
        signoffReportPass("learn", "analytical_pex"),
      detail: "Sakurai–Tamaru + FDM 2D · Raphael GAP",
      action: "analytical_pex",
      href: "/tools?tab=run&action=analytical_pex",
    },
    {
      id: "inspect",
      label: "Inspect ODB/STA/Yosys",
      group: "Analisi",
      ok: has("1_synth.odb"),
      detail: "GET /api/inspect",
      href: "/tools?stage=synth&tab=results#inspect",
    },
    {
      id: "docs",
      label: "Extended flow docs",
      group: "Course",
      ok: fs.existsSync(path.join(LEARN_ROOT, "reference/extended-flow.md")),
      detail: "tool-hooks + extended-flow",
      href: "/materials/reference/extended-flow.md",
    },
  ];

  const lessonsDone = (progress.completed_lessons ?? []).length;
  const readyHooks = hooks.filter((h) => h.ok).length;
  // Core wiring (not full PD finish): environment + frontend + analysis + docs
  const coreIds = [
    "toolchain",
    "iverilog",
    "rtl",
    "rtl_sim",
    "inspect",
    "or-web",
    "docs",
  ];
  const wired = coreIds.every((id) => hooks.find((h) => h.id === id)?.ok);

  return {
    ready: wired,
    summary: {
      hooksOk: readyHooks,
      hooksTotal: hooks.length,
      lessonsDone,
      lessonsTotal: LESSONS.length,
      lock,
      viewerRunning: viewer.running,
      recentJobs: jobs.length,
      pipelineReady: pipeline.filter((p) => p.ready).length,
      wired,
    },
    tools,
    hooks,
    pipeline,
    display,
    viewer,
  };
}

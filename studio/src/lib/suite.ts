import fs from "fs";
import path from "path";
import { LEARN_ROOT, REPO_ROOT, LESSONS, readProgress } from "./course";
import { artifactExists, detectDisplay, listOpenTargets, resultsDir } from "./open";
import { viewerStatus } from "./webviewer";
import { listJobs, readLock, getPipelineStatus } from "./jobs";
import { probeToolchain } from "./run";
import { isCurrentReport, isCurrentRunArtifact } from "./liveReports";
import {
  drcSignoffHookDetail,
  hookLeftoverIds,
  klayoutDrcHookDetail,
  lvsSignoffHookDetail,
  powerSignoffHookDetail,
  signoffAllHookDetail,
  staSignoffHookDetail,
} from "./leftoverCatalog";

export type HookStatus = {
  id: string;
  label: string;
  group: string;
  ok: boolean;
  /** Normalized report state when this hook is backed by a live report. */
  status?: "PASS" | "FAIL" | "WARN" | "PARTIAL" | "PROXY" | "GAP" | "NOT_RUN";
  detail: string;
  action?: string;
  href?: string;
  leftover?: { ids: string[] };
};

function has(rel: string) {
  return artifactExists(rel);
}

function signoffReportPass(variant: string, name: string) {
  const p = path.join(LEARN_ROOT, "sim/reports", `${name}_${variant}.json`);
  if (!isCurrentReport(p)) return false;
  try {
    const j = JSON.parse(fs.readFileSync(p, "utf8")) as { ok?: boolean };
    return j.ok === true;
  } catch {
    return false;
  }
}

type LiveReport = {
  status?: unknown;
  ok?: unknown;
  summary?: unknown;
  reason?: unknown;
};

const REPORT_STATUSES = new Set([
  "PASS",
  "FAIL",
  "WARN",
  "PARTIAL",
  "PROXY",
  "GAP",
  "NOT_RUN",
]);

function readCurrentReport(relativePath: string): LiveReport | null {
  const reportPath = path.join(LEARN_ROOT, "sim/reports", relativePath);
  if (!isCurrentReport(reportPath)) return null;
  try {
    const raw = JSON.parse(fs.readFileSync(reportPath, "utf8")) as unknown;
    return raw && typeof raw === "object" ? (raw as LiveReport) : null;
  } catch {
    return null;
  }
}

function reportStatus(report: LiveReport | null): HookStatus["status"] | undefined {
  if (!report) return undefined;
  const value = String(report.status || "").toUpperCase();
  if (REPORT_STATUSES.has(value)) return value as HookStatus["status"];
  return report.ok === true ? "PASS" : undefined;
}

function reportDetail(report: LiveReport | null, fallback: string): string {
  const status = reportStatus(report);
  const text = String(report?.summary || report?.reason || "").trim();
  if (!status) return fallback;
  if (!text) return `${status} · ${fallback}`;
  return text.toUpperCase().includes(status) ? text : `${status} · ${text}`;
}

/** Current-run I(t) result for at least one supported design variant. */
function currentRunDynamicIrPresent() {
  for (const variant of ["flowlab", "learn"]) {
    const report = readCurrentReport(`dynamic_ir_${variant}_direct.json`);
    if (report?.ok === true) return true;
  }
  return false;
}

function currentReportFor(
  names: (variant: string) => string,
): { report: LiveReport; status: NonNullable<HookStatus["status"]> } | null {
  for (const variant of ["flowlab", "learn"]) {
    const report = readCurrentReport(names(variant));
    const status = reportStatus(report);
    if (report && status) return { report, status };
  }
  return null;
}

function withLeftover(hook: HookStatus): HookStatus {
  const ids = hookLeftoverIds(hook.id, hook.detail);
  if (!ids.length) return hook;
  return { ...hook, leftover: { ids } };
}

function vygesEmHookDetail() {
  for (const variant of ["flowlab", "learn"]) {
    const report = readCurrentReport(`vyges_em_ir_${variant}.json`);
    if (!report) continue;
    try {
      const j = report as LiveReport & {
        vyges?: { em_checked?: number; ir_met?: boolean };
        summary?: string;
      };
      const em = j.vyges?.em_checked;
      const irMet = j.vyges?.ir_met;
      if (em === 0 || irMet === false) {
        return `engine ran · em_checked ${em ?? 0} (no emlimit) · ir_met ${irMet === false ? "false" : String(irMet)}`;
      }
      if (j.summary) return reportDetail(report, String(j.summary));
    } catch {
      /* ignore */
    }
  }
  return "Apache-2.0 binary · CG + backward Euler · em_checked stays 0 without emlimit";
}

function thermalHookDetail() {
  for (const variant of ["flowlab", "learn"]) {
    const p = path.join(LEARN_ROOT, "sim/reports", `thermal_signoff_${variant}.json`);
    if (!isCurrentReport(p)) continue;
    try {
      const j = JSON.parse(fs.readFileSync(p, "utf8")) as {
        thermal?: { t_max_c?: number };
      };
      const t = j.thermal?.t_max_c;
      if (typeof t === "number" && Number.isFinite(t)) {
        return `HotSpot t_max ${t.toFixed(2)} °C · architecture compact model`;
      }
    } catch {
      /* ignore */
    }
  }
  return "HotSpot architecture compact model · run_thermal_signoff.sh";
}

function powerReportOk(variant: string, name: string) {
  return isCurrentRunArtifact(
    path.join(LEARN_ROOT, "sim/reports", `${name}_${variant}.log`),
    variant,
  );
}

function systemPdnHookDetail(): string {
  for (const variant of ["flowlab", "learn"]) {
    const report = readCurrentReport(`system_pdn_${variant}.json`);
    if (!report) continue;
    try {
      const system = report as LiveReport & Record<string, unknown>;
      if (system.status === "GAP") {
        return `GAP System PDN · ${String(system.reason ?? "optional engine unavailable")}`;
      }
      if (typeof system.summary === "string" && system.summary.trim()) return reportDetail(report, system.summary);
    } catch {
      // Try the other supported variant.
    }
  }
  return "System PDN status is read from the current report";
}

function powerChainOk() {
  for (const v of ["flowlab", "learn"]) {
    const log = path.join(LEARN_ROOT, `sim/reports/power_chain_${v}.log`);
    if (isCurrentRunArtifact(log, v)) {
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
  const toolOk = (name: string) =>
    tools.tools.some((tool) => tool.name === name && tool.ok);
  const display = detectDisplay();
  const viewer = await viewerStatus();
  const lock = readLock();
  const jobs = listJobs(5);
  const pipeline = getPipelineStatus();
  const progress = readProgress();
  const open = listOpenTargets();

  const hooks: HookStatus[] = [
    {
      id: "toolchain",
      label: "Toolchain core",
      group: "Environment",
      ok: tools.tools.filter((t) => ["openroad", "yosys", "sta", "klayout"].includes(t.name)).every((t) => t.ok) && tools.orfs,
      detail: tools.tools.map((t) => `${t.name}:${t.ok ? "ok" : "no"}`).join(" · "),
      href: "/tools",
    },
    {
      id: "magic_netgen",
      label: "Magic / Netgen",
      group: "Environment",
      ok: toolOk("magic") && (toolOk("netgen") || toolOk("netgen-lvs")),
      detail: toolOk("magic")
        ? "present · Nangate LVS stays on KLayout (no FreePDK45 .tech)"
        : "not registered · Nangate LVS stays on KLayout (no FreePDK45 .tech)",
      action: "layout_tools",
    },
    {
      id: "ngspice",
      label: "ngspice (System PDN)",
      group: "Environment",
      ok: toolOk("ngspice"),
      detail: toolOk("ngspice")
        ? toolOk("xyce")
          ? "ngspice present · Xyce READY"
          : "ngspice present · Xyce install via install_xyce.sh"
        : "GAP ngspice · optional System PDN is unavailable until the engine is installed",
      action: "system_pdn",
    },
    {
      id: "iverilog",
      label: "Icarus (RTL + gate sim)",
      group: "Environment",
      ok: toolOk("iverilog"),
      detail: toolOk("iverilog") ? "iverilog present" : "install iverilog",
      action: "rtl_sim",
    },
    {
      id: "hotspot",
      label: "HotSpot (thermal)",
      group: "Environment",
      ok: toolOk("hotspot"),
      detail: "UVA HotSpot architecture compact model",
      action: "thermal_signoff",
    },
    {
      id: "fastercap",
      label: "FasterCap (PEX BEM)",
      group: "Environment",
      ok: toolOk("fastercap"),
      detail: "LGPL 3D BEM · 2-wire educational extract, not Raphael",
      action: "analytical_pex",
    },
    {
      id: "ccs_char",
      label: "CCS char (PTM GCD cells)",
      group: "Environment",
      ok:
        signoffReportPass("flowlab", "ccs_char") ||
        signoffReportPass("learn", "ccs_char"),
      detail: "ngspice + PTM 45 nm sidecar on GCD cells · official Nangate liberty stays NLDM",
      action: "ccs_char",
      href: "/tools?tab=run&action=ccs_char",
    },
    {
      id: "display",
      label: "DISPLAY / Desktop",
      group: "Environment",
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
      ok: toolOk("iverilog") && fs.existsSync(path.join(LEARN_ROOT, "sim/gcd/tb_gcd.v")),
      detail: "run_rtl_sim.sh · rtl_sim action · lesson 00",
      action: "rtl_sim",
      href: "/tools?tab=run&action=rtl_sim",
    },
    {
      id: "gate_sim",
      label: "Gate sim + VCD name-join",
      group: "Frontend",
      ok:
        toolOk("iverilog") &&
        fs.existsSync(path.join(LEARN_ROOT, "sim/gcd/tb_gcd_gate.v")) &&
        fs.existsSync(path.join(LEARN_ROOT, "platforms/nangate45/verilog/NangateOpenCellLibrary.v")),
      detail: "run_gate_sim.sh · 6_final.v + Nangate .v · prefers gcd_gate.vcd",
      action: "gate_sim",
      href: "/tools?tab=run&action=gate_sim",
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
        signoffReportPass("flowlab", "system_pdn") ||
        signoffReportPass("learn", "system_pdn"),
      status: currentReportFor((variant) => `system_pdn_${variant}.json`)?.status,
      detail: systemPdnHookDetail(),
      action: "system_pdn",
      href: "/pkg",
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
      detail: "Gate VCD if gate_sim · else RTL · report_power → I_avg",
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
        signoffReportPass("flowlab", "pdn_chip_ir") ||
        signoffReportPass("learn", "pdn_chip_ir"),
      status: currentReportFor((variant) => `pdn_chip_ir_${variant}.json`)?.status,
      detail: reportDetail(
        currentReportFor((variant) => `pdn_chip_ir_${variant}.json`)?.report ?? null,
        "write_pg_spice · pdn_transient · finish IR ledger",
      ),
      action: "chip_pdn_ir",
      href: "/flow?phase=finish#ir",
    },
    {
      id: "vyges_em_ir",
      label: "vyges-em-ir",
      group: "Power",
      ok:
        signoffReportPass("flowlab", "vyges_em_ir") ||
        signoffReportPass("learn", "vyges_em_ir"),
      status: currentReportFor((variant) => `vyges_em_ir_${variant}.json`)?.status,
      detail: vygesEmHookDetail(),
      action: "vyges_em_ir",
      href: "/flow?phase=finish#ir",
    },
    {
      id: "dynamic_ir",
      label: "Dynamic IR I(t)",
      group: "Power",
      ok: currentRunDynamicIrPresent(),
      status: currentReportFor((variant) => `dynamic_ir_${variant}_direct.json`)?.status,
      detail: reportDetail(
        currentReportFor((variant) => `dynamic_ir_${variant}_direct.json`)?.report ?? null,
        "current-run _direct.json · solver deltas use the same live mesh",
      ),
      action: "dynamic_ir",
      href: "/flow?phase=finish#ir",
    },
    {
      id: "dse",
      label: "DSE (proposer)",
      group: "Lab",
      ok:
        signoffReportPass("flowlab", "dse") || signoffReportPass("learn", "dse"),
      detail: "Proposer only — does not run signoff_all",
      href: "/lab",
    },
    {
      id: "power_chain",
      label: "SPICE chain",
      group: "Power",
      ok: powerChainOk(),
      detail: "activity → chip IR → export; System PDN is PKG",
      action: "power_chain",
      href: "/tools?tab=run&action=power_chain",
    },
    {
      id: "spice_lab",
      label: "SPICE lab export",
      group: "Power",
      ok: isCurrentRunArtifact(
        path.join(LEARN_ROOT, "sim/spice/INDEX_flowlab.md"),
        "flowlab",
      ),
      detail: "export_spice_lab · mesh_stats + netlist",
      action: "export_spice_lab",
      href: "/tools?tab=run&action=export_spice_lab",
    },
    {
      id: "klayout_drc",
      label: "KLayout DRC",
      group: "Signoff",
      ok: has("6_final.gds"),
      detail: klayoutDrcHookDetail(),
      action: "klayout_drc",
      href: "/tools?tab=run&action=klayout_drc",
    },
    {
      id: "sta_signoff",
      label: "STA signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "sta_signoff") || signoffReportPass("learn", "sta_signoff"),
      detail: staSignoffHookDetail(),
      action: "sta_signoff",
      href: "/flow?phase=finish",
    },
    {
      id: "sta_ir_aware",
      label: "STA IR-aware",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "sta_ir_aware") || signoffReportPass("learn", "sta_ir_aware"),
      detail: "NLDM path × per-cell ITerm V · educational, not Tempus",
      action: "sta_ir_aware",
      href: "/flow?phase=finish#sta-ir",
    },
    {
      id: "drc_signoff",
      label: "DRC signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "drc_signoff") || signoffReportPass("learn", "drc_signoff"),
      detail: drcSignoffHookDetail(),
      action: "drc_signoff",
      href: "/flow?phase=finish",
    },
    {
      id: "lvs_signoff",
      label: "LVS signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "lvs_signoff") || signoffReportPass("learn", "lvs_signoff"),
      detail: lvsSignoffHookDetail(),
      action: "klayout_lvs",
      href: "/flow?phase=finish",
    },
    {
      id: "power_signoff",
      label: "Power signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "power_signoff") || signoffReportPass("learn", "power_signoff"),
      detail: powerSignoffHookDetail(),
      action: "power_signoff",
      href: "/flow?phase=finish#ir",
    },
    {
      id: "signoff_all",
      label: "Full signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "signoff_all") || signoffReportPass("learn", "signoff_all"),
      detail: signoffAllHookDetail(),
      action: "signoff_all",
      href: "/flow?phase=finish#signoff",
    },
    {
      id: "eco",
      label: "ECO loop",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "eco") || signoffReportPass("learn", "eco"),
      detail: "Propose on flowlab. Apply/close only on eco_scratch. Copy and leftover status come from the current signoff report. Does not skip signoff_all.",
      action: "eco",
      href: "/flow?phase=finish#eco",
    },
    {
      id: "thermal_signoff",
      label: "Thermal (HotSpot)",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "thermal_signoff") || signoffReportPass("learn", "thermal_signoff"),
      detail: thermalHookDetail(),
      action: "thermal_signoff",
      href: "/pkg",
    },
    {
      id: "pkg_rdl",
      label: "PKG RDL (dummy)",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "pkg_rdl") || signoffReportPass("learn", "pkg_rdl"),
      detail: "rdl_route on sidecar ODB · dummy bump LEF, not C4",
      action: "pkg_rdl",
      href: "/pkg",
    },
    {
      id: "pkg_signoff",
      label: "PKG signoff",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "pkg_signoff") || signoffReportPass("learn", "pkg_signoff"),
      detail: "Bump + system PDN + dummy rdl_route",
      action: "pkg_signoff",
      href: "/pkg",
    },
    {
      id: "signoff_phase2",
      label: "Signoff Phase 2",
      group: "Signoff",
      ok: signoffReportPass("flowlab", "signoff_phase2") || signoffReportPass("learn", "signoff_phase2"),
      detail: "HotSpot + PKG orchestrator",
      action: "signoff_phase2",
      href: "/pkg",
    },
    {
      id: "spice_engines",
      label: "SPICE engines",
      group: "Environment",
      ok: signoffReportPass("flowlab", "spice_engines") || signoffReportPass("learn", "spice_engines"),
      detail: "ngspice + Xyce N4 same-run reference · run_spice_engines.sh",
      action: "spice_engines",
      href: "/tools?tab=run&action=spice_engines",
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
      label: "Yosys equiv",
      group: "Analysis",
      ok:
        signoffReportPass("flowlab", "yosys_equiv") ||
        signoffReportPass("learn", "yosys_equiv"),
      detail: "RTL ↔ generic synth · equiv_induct",
      action: "yosys_equiv",
      href: "/tools?tab=run&action=yosys_equiv",
    },
    {
      id: "formal_gcd",
      label: "Formal SAT",
      group: "Analysis",
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
      group: "Analysis",
      ok:
        signoffReportPass("flowlab", "openrcx") ||
        signoffReportPass("learn", "openrcx"),
      detail: "OpenRCX SPEF · 6_final.spef",
      action: "openrcx_report",
      href: "/tools?tab=run&action=openrcx_report",
    },
    {
      id: "analytical_pex",
      label: "Analytical PEX + FasterCap",
      group: "Analysis",
      ok:
        signoffReportPass("flowlab", "analytical_pex") ||
        signoffReportPass("learn", "analytical_pex"),
      detail: "Sakurai–Tamaru + FDM 2D + FasterCap BEM · Raphael GAP",
      action: "analytical_pex",
      href: "/tools?tab=run&action=analytical_pex",
    },
    {
      id: "ccs_char_report",
      label: "CCS sidecar liberty",
      group: "Analysis",
      ok:
        signoffReportPass("flowlab", "ccs_char") ||
        signoffReportPass("learn", "ccs_char"),
      detail: "GCD-cell output_current from SPICE · not foundry CCS",
      action: "ccs_char",
      href: "/tools?tab=run&action=ccs_char",
    },
    // ASAP7 lab hooks live on /lab — not course suite hub
    {
      id: "lvs_deep",
      label: "Deep LVS (filter + VTL)",
      group: "Analysis",
      ok: isCurrentReport(path.join(LEARN_ROOT, "sim/reports/lvs_deep_flowlab.json")),
      detail: "Filtered CDL + well→VDD/VSS · match required · FILL/TAP abstract · current must-connect result",
      action: "lvs_deep",
      href: "/tools?tab=run&action=lvs_deep",
    },
    {
      id: "inspect",
      label: "Inspect ODB/STA/Yosys",
      group: "Analysis",
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

  const hooksWithLeftover = hooks.map((hook) => withLeftover(hook));

  const lessonsDone = (progress.completed_lessons ?? []).length;
  const readyHooks = hooksWithLeftover.filter((h) => h.ok).length;
  // Core wiring (not full PD finish): environment + frontend + analysis + docs
  const coreIds = [
    "toolchain",
    "iverilog",
    "rtl",
    "rtl_sim",
    "gate_sim",
    "inspect",
    "or-web",
    "docs",
  ];
  const wired = coreIds.every((id) => hooksWithLeftover.find((h) => h.id === id)?.ok);

  return {
    ready: wired,
    summary: {
      hooksOk: readyHooks,
      hooksTotal: hooksWithLeftover.length,
      lessonsDone,
      lessonsTotal: LESSONS.length,
      lock,
      viewerRunning: viewer.running,
      recentJobs: jobs.length,
      pipelineReady: pipeline.filter((p) => p.ready).length,
      wired,
    },
    tools,
    hooks: hooksWithLeftover,
    pipeline,
    display,
    viewer,
  };
}

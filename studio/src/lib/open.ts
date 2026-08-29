import fs from "fs";
import path from "path";
import { spawn } from "child_process";
import { REPO_ROOT, LEARN_ROOT } from "./course";

const DEFAULT_VARIANT = "learn";

export function resultsDir(variant: string = DEFAULT_VARIANT) {
  return path.join(
    /*turbopackIgnore: true*/ REPO_ROOT,
    `tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${variant}`,
  );
}

export function flowDir() {
  return path.join(
    /*turbopackIgnore: true*/ REPO_ROOT,
    "tools/OpenROAD-flow-scripts/flow",
  );
}

/** Default OpenROAD GUI targets per pipeline stage (ORFS make gui_*). */
export const STAGE_GUI_TARGETS: Record<
  string,
  { id: string; label: string; artifact: string; kind: "openroad" | "klayout" }[]
> = {
  synth: [
    {
      id: "gui-synth",
      label: "OpenROAD · 1_synth.odb",
      artifact: "1_synth.odb",
      kind: "openroad",
    },
  ],
  floorplan: [
    {
      id: "gui-fp",
      label: "OpenROAD · floorplan",
      artifact: "2_1_floorplan.odb",
      kind: "openroad",
    },
    {
      id: "gui-pdn",
      label: "OpenROAD · PDN",
      artifact: "2_4_floorplan_pdn.odb",
      kind: "openroad",
    },
  ],
  place: [
    {
      id: "gui-gp",
      label: "OpenROAD · global place",
      artifact: "3_3_place_gp.odb",
      kind: "openroad",
    },
    {
      id: "gui-dp",
      label: "OpenROAD · detailed place",
      artifact: "3_5_place_dp.odb",
      kind: "openroad",
    },
  ],
  cts: [
    {
      id: "gui-cts",
      label: "OpenROAD · CTS",
      artifact: "4_cts.odb",
      kind: "openroad",
    },
  ],
  route: [
    {
      id: "gui-grt",
      label: "OpenROAD · global route",
      artifact: "5_1_grt.odb",
      kind: "openroad",
    },
    {
      id: "gui-drt",
      label: "OpenROAD · detailed route",
      artifact: "5_2_route.odb",
      kind: "openroad",
    },
  ],
  finish: [
    {
      id: "gui-final",
      label: "OpenROAD · final",
      artifact: "6_final.odb",
      kind: "openroad",
    },
    {
      id: "klayout-gds",
      label: "KLayout · 6_final.gds",
      artifact: "6_final.gds",
      kind: "klayout",
    },
  ],
};

export type OpenTarget = {
  id: string;
  label: string;
  kind:
    | "openroad"
    | "klayout"
    | "dashboard"
    | "gallery"
    | "doc"
    | "lesson"
    | "run"
    | "webviewer";
  href?: string;
  artifact?: string;
  absPath?: string;
  exists: boolean;
  stage?: string;
  command?: string;
  action?: string;
};

export function detectDisplay(): string | null {
  const d = process.env.DISPLAY || process.env.STUDIO_DISPLAY;
  if (d) return d;
  // Common cloud Desktop socket
  if (fs.existsSync("/tmp/.X11-unix/X1")) return ":1";
  if (fs.existsSync("/tmp/.X11-unix/X0")) return ":0";
  return null;
}

function absArtifact(name: string, variant = DEFAULT_VARIANT) {
  return path.join(resultsDir(variant), name);
}

function openroadCommand(abs: string): string {
  const tcl = path.join(LEARN_ROOT, "scripts/gui_session.tcl");
  if (fs.existsSync(tcl)) {
    return `ODB_FILE=${abs} DISPLAY=\${DISPLAY:-:1} openroad -gui -no_splash -no_init ${tcl}`;
  }
  return `DISPLAY=\${DISPLAY:-:1} openroad -gui -no_splash ${abs}`;
}

function klayoutCommand(abs: string): string {
  return `DISPLAY=\${DISPLAY:-:1} klayout ${abs}`;
}

export function listOpenTargets(): {
  display: string | null;
  targets: OpenTarget[];
} {
  const display = detectDisplay();
  const targets: OpenTarget[] = [];

  // In-app dashboards
  for (const stage of Object.keys(STAGE_GUI_TARGETS)) {
    targets.push({
      id: `dash-${stage}`,
      label: `Dashboard risultati · ${stage}`,
      kind: "dashboard",
      href: `/strumenti?stage=${stage}&tab=results`,
      exists: true,
      stage,
    });
    targets.push({
      id: `run-${stage}`,
      label: `Console run · ${stage}`,
      kind: "dashboard",
      href: `/strumenti?stage=${stage}&tab=run&action=${stage}`,
      exists: true,
      stage,
    });
  }

  targets.push({
    id: "dash-ops",
    label: "Ops · pipeline & job",
    kind: "dashboard",
    href: "/strumenti?tab=ops",
    exists: true,
  });
  targets.push({
    id: "dash-inspect",
    label: "Ispezione tool (STA / ODB / Yosys)",
    kind: "dashboard",
    href: "/strumenti?stage=synth&tab=results#inspect",
    exists: true,
  });
  targets.push({
    id: "dash-suite",
    label: "Suite collaborativa · stato hook",
    kind: "dashboard",
    href: "/strumenti#suite",
    exists: true,
  });
  targets.push({
    id: "dash-flowlab",
    label: "FlowLab · RTL → GDSII",
    kind: "dashboard",
    href: "/flusso",
    exists: true,
  });
  targets.push({
    id: "dash-pkg",
    label: "PKG · design package & System PDN",
    kind: "dashboard",
    href: "/pkg",
    exists: true,
  });

  // Extended / analysis run actions (deep-link to LiveRunConsole)
  const runActions: { id: string; label: string; action: string }[] = [
    { id: "run-check", label: "Run · verifica toolchain", action: "check" },
    { id: "run-rtl-sim", label: "Run · sim RTL (Icarus)", action: "rtl_sim" },
    { id: "run-gridcheck", label: "Run · gridcheck PDN", action: "gridcheck" },
    { id: "run-system-pdn", label: "Run · System PDN (hier)", action: "system_pdn" },
    { id: "run-chip-ir", label: "Run · chip IR mesh", action: "chip_pdn_ir" },
    { id: "run-vyges-em-ir", label: "Run · vyges-em-ir", action: "vyges_em_ir" },
    { id: "run-power-chain", label: "Run · catena SPICE", action: "power_chain" },
    {
      id: "run-export-spice",
      label: "Run · export SPICE lab",
      action: "export_spice_lab",
    },
    {
      id: "run-activity",
      label: "Run · activity → power",
      action: "activity_power",
    },
    {
      id: "run-vectorless",
      label: "Run · vectorless / dynamic IR",
      action: "vectorless",
    },
    {
      id: "run-yosys-equiv",
      label: "Run · Yosys equiv (EQY-class)",
      action: "yosys_equiv",
    },
    {
      id: "run-formal",
      label: "Run · formal SAT GCD",
      action: "formal_gcd",
    },
    {
      id: "run-openrcx",
      label: "Run · OpenRCX SPEF report",
      action: "openrcx_report",
    },
    {
      id: "run-analytical-pex",
      label: "Run · PEX analitico FasterCap-class",
      action: "analytical_pex",
    },
    {
      id: "run-tool-matrix",
      label: "Run · tool matrix OSS",
      action: "tool_matrix",
    },
    { id: "run-klayout-drc", label: "Run · KLayout DRC", action: "klayout_drc" },
    { id: "run-test-course", label: "Run · smoke corso", action: "test_course" },
  ];
  for (const r of runActions) {
    targets.push({
      id: r.id,
      label: r.label,
      kind: "run",
      href: `/strumenti?tab=run&action=${r.action}`,
      exists: true,
      action: r.action,
    });
  }

  for (const stage of Object.keys(STAGE_GUI_TARGETS)) {
    const primary = STAGE_GUI_TARGETS[stage].find((t) => t.kind === "openroad");
    const exists = primary
      ? fs.existsSync(absArtifact(primary.artifact))
      : false;
    targets.push({
      id: `web-${stage}`,
      label: `OpenROAD Web Viewer · ${stage}`,
      kind: "webviewer",
      href: `/strumenti?stage=${stage}&tab=results#inspect`,
      exists,
      stage,
      artifact: primary?.artifact,
    });
  }
  targets.push({
    id: "gallery",
    label: "Galleria GUI (screenshot)",
    kind: "gallery",
    href: "/materiali?tab=gallery",
    exists: true,
  });
  targets.push({
    id: "golden",
    label: "Golden metrics",
    kind: "doc",
    href: "/materiali/reference/golden-metrics.md",
    exists: true,
  });
  targets.push({
    id: "atlas",
    label: "Atlante GUI",
    kind: "doc",
    href: "/materiali/reference/gui-atlas.md",
    exists: true,
  });
  targets.push({
    id: "hooks",
    label: "Tool hooks (OpenROAD/STA/Yosys)",
    kind: "doc",
    href: "/materiali/reference/tool-hooks.md",
    exists: true,
  });
  targets.push({
    id: "oss-integrations",
    label: "Matrice integrazioni OSS",
    kind: "doc",
    href: "/materiali/reference/oss-integrations.md",
    exists: true,
  });
  targets.push({
    id: "vectorless-power",
    label: "Vectorless / dynamic power",
    kind: "doc",
    href: "/materiali/reference/vectorless-power.md",
    exists: true,
  });
  targets.push({
    id: "extended-flow",
    label: "Extended flow map",
    kind: "doc",
    href: "/materiali/reference/extended-flow.md",
    exists: true,
  });

  // Lessons
  const lessons = [
    "00-intro",
    "01-constraints",
    "02-synthesis",
    "03-floorplan",
    "04-placement",
    "05-cts",
    "06-routing",
    "07-finish",
  ];
  for (const id of lessons) {
    targets.push({
      id: `lesson-${id}`,
      label: `Lezione ${id}`,
      kind: "lesson",
      href: `/lezioni/${id}`,
      exists: true,
    });
  }

  // External viewers
  for (const [stage, items] of Object.entries(STAGE_GUI_TARGETS)) {
    for (const item of items) {
      const abs = absArtifact(item.artifact);
      const exists = fs.existsSync(abs);
      targets.push({
        id: item.id,
        label: item.label,
        kind: item.kind,
        artifact: item.artifact,
        absPath: abs,
        exists,
        stage,
        command:
          item.kind === "klayout" ? klayoutCommand(abs) : openroadCommand(abs),
      });
    }
  }

  return { display, targets };
}

export function resolveOpenTarget(id: string): OpenTarget | null {
  return listOpenTargets().targets.find((t) => t.id === id) ?? null;
}

export function resolveArtifactOpen(
  artifact: string,
  variant = DEFAULT_VARIANT,
): OpenTarget | null {
  const name = path.basename(artifact);
  const abs = absArtifact(name, variant);
  if (!fs.existsSync(abs)) return null;
  if (name.endsWith(".gds") || name.endsWith(".oas")) {
    return {
      id: `file-${name}`,
      label: `KLayout · ${name}`,
      kind: "klayout",
      artifact: name,
      absPath: abs,
      exists: true,
      command: klayoutCommand(abs),
    };
  }
  if (name.endsWith(".odb")) {
    return {
      id: `file-${name}`,
      label: `OpenROAD · ${name}`,
      kind: "openroad",
      artifact: name,
      absPath: abs,
      exists: true,
      command: openroadCommand(abs),
    };
  }
  return null;
}

export type LaunchResult = {
  ok: boolean;
  launched: boolean;
  message: string;
  command?: string;
  display?: string | null;
  pid?: number;
};

export function launchExternal(target: OpenTarget): LaunchResult {
  const display = detectDisplay();
  if (!target.absPath || !target.exists) {
    return {
      ok: false,
      launched: false,
      message: `Artefatto mancante: ${target.artifact ?? target.id}`,
      command: target.command,
      display,
    };
  }
  if (!display) {
    return {
      ok: false,
      launched: false,
      message:
        "Nessun DISPLAY (apri Desktop su cursor.com/agents). Comando pronto da copiare.",
      command: target.command,
      display: null,
    };
  }

  try {
    if (target.kind === "klayout") {
      const child = spawn("klayout", [target.absPath], {
        env: { ...process.env, DISPLAY: display },
        detached: true,
        stdio: "ignore",
      });
      child.unref();
      return {
        ok: true,
        launched: true,
        message: `KLayout avviato su ${target.artifact}`,
        command: target.command,
        display,
        pid: child.pid,
      };
    }

    if (target.kind === "openroad") {
      const tcl = path.join(LEARN_ROOT, "scripts/gui_session.tcl");
      const args = fs.existsSync(tcl)
        ? ["-gui", "-no_splash", "-no_init", tcl]
        : ["-gui", "-no_splash"];
      const child = spawn("openroad", args, {
        env: {
          ...process.env,
          DISPLAY: display,
          ODB_FILE: target.absPath,
          GUI_VIEW: "all",
        },
        detached: true,
        stdio: "ignore",
        cwd: flowDir(),
      });
      child.unref();
      return {
        ok: true,
        launched: true,
        message: `OpenROAD GUI avviata su ${target.artifact} (Desktop)`,
        command: target.command,
        display,
        pid: child.pid,
      };
    }

    return {
      ok: false,
      launched: false,
      message: "Target non lanciabile esternamente",
      display,
    };
  } catch (e) {
    return {
      ok: false,
      launched: false,
      message: e instanceof Error ? e.message : String(e),
      command: target.command,
      display,
    };
  }
}

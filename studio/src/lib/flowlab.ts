import fs from "fs";
import path from "path";
import { LEARN_ROOT, REPO_ROOT } from "./course";
import { listJobs } from "./jobs";

export const FLOWLAB_VARIANT = "flowlab";
export const FLOWLAB_DIR = path.join(LEARN_ROOT, "flowlab");
export const FLOWLAB_RTL = path.join(FLOWLAB_DIR, "gcd.v");
export const FLOWLAB_PARAMS = path.join(FLOWLAB_DIR, "params.json");

const UPSTREAM_RTL = path.join(
  REPO_ROOT,
  "tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v",
);

export type SdcPreset = "default" | "relaxed" | "tight";

export type FlowlabParams = {
  coreUtilization: number;
  placeDensityAddon: number;
  abcArea: 0 | 1;
  sdcPreset: SdcPreset;
  tnsEndPercent: number;
};

export const DEFAULT_PARAMS: FlowlabParams = {
  coreUtilization: 35,
  placeDensityAddon: 0.2,
  abcArea: 1,
  sdcPreset: "default",
  tnsEndPercent: 100,
};

const SDC_MAP: Record<SdcPreset, string> = {
  default: "./designs/nangate45/gcd-tutorial/constraint.sdc",
  relaxed: "./designs/nangate45/gcd-tutorial/constraint_relaxed.sdc",
  tight: "./designs/nangate45/gcd-tutorial/constraint_tight.sdc",
};

export const FLOW_PHASES = [
  {
    id: "rtl",
    label: "RTL",
    title: "Scrivi e simula RTL",
    action: "rtl_sim" as const,
    hint: "Editor Verilog · Icarus",
  },
  {
    id: "synth",
    label: "Sintesi",
    title: "Sintesi logica (Yosys)",
    action: "synth" as const,
    hint: "ABC area · SDC",
  },
  {
    id: "floorplan",
    label: "Floorplan",
    title: "Floorplan e die",
    action: "floorplan" as const,
    hint: "Utilizzo core",
  },
  {
    id: "pdn",
    label: "PDN",
    title: "Analisi chip PDN",
    action: "gridcheck" as const,
    hint: "check_power_grid",
  },
  {
    id: "place",
    label: "Place",
    title: "Placement",
    action: "place" as const,
    hint: "Densità",
  },
  {
    id: "cts",
    label: "CTS",
    title: "Clock tree",
    action: "cts" as const,
    hint: "TNS end %",
  },
  {
    id: "route",
    label: "Route",
    title: "Routing",
    action: "route" as const,
    hint: "Global + detailed",
  },
  {
    id: "finish",
    label: "GDSII",
    title: "Finish · GDS",
    action: "finish" as const,
    hint: "SPEF · GDS · signoff",
  },
  {
    id: "pkg",
    label: "PKG",
    title: "Package · System PDN",
    action: "system_pdn" as const,
    hint: "BUMPS · STRAPS · FULL",
  },
] as const;

export type FlowPhaseId = (typeof FLOW_PHASES)[number]["id"];

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

export function normalizeParams(raw: Partial<FlowlabParams> | null): FlowlabParams {
  const p = { ...DEFAULT_PARAMS, ...(raw ?? {}) };
  const sdc =
    p.sdcPreset === "relaxed" || p.sdcPreset === "tight" ? p.sdcPreset : "default";
  return {
    coreUtilization: clamp(Number(p.coreUtilization) || 35, 20, 60),
    placeDensityAddon: clamp(Number(p.placeDensityAddon) || 0.2, 0.05, 0.45),
    abcArea: p.abcArea === 0 ? 0 : 1,
    sdcPreset: sdc,
    tnsEndPercent: clamp(Number(p.tnsEndPercent) || 100, 0, 100),
  };
}

export function ensureFlowlabWorkspace() {
  fs.mkdirSync(/*turbopackIgnore: true*/ FLOWLAB_DIR, { recursive: true });
  if (!fs.existsSync(FLOWLAB_RTL)) {
    if (!fs.existsSync(UPSTREAM_RTL)) {
      throw new Error(`RTL upstream mancante: ${UPSTREAM_RTL}`);
    }
    fs.copyFileSync(UPSTREAM_RTL, FLOWLAB_RTL);
  }
  if (!fs.existsSync(FLOWLAB_PARAMS)) {
    writeParams(DEFAULT_PARAMS);
  }
}

export function readRtl(): string {
  ensureFlowlabWorkspace();
  return fs.readFileSync(/*turbopackIgnore: true*/ FLOWLAB_RTL, "utf8");
}

export function writeRtl(source: string) {
  ensureFlowlabWorkspace();
  if (!source || source.trim().length < 20) {
    throw new Error("RTL troppo corto o vuoto");
  }
  if (!/\bmodule\s+\w+/i.test(source)) {
    throw new Error("RTL senza dichiarazione module");
  }
  fs.writeFileSync(
    /*turbopackIgnore: true*/ FLOWLAB_RTL,
    source.endsWith("\n") ? source : source + "\n",
    "utf8",
  );
}

export function resetRtl(): string {
  ensureFlowlabWorkspace();
  if (!fs.existsSync(UPSTREAM_RTL)) {
    throw new Error("RTL golden mancante");
  }
  fs.copyFileSync(UPSTREAM_RTL, FLOWLAB_RTL);
  return readRtl();
}

export function readParams(): FlowlabParams {
  ensureFlowlabWorkspace();
  try {
    const raw = JSON.parse(
      fs.readFileSync(/*turbopackIgnore: true*/ FLOWLAB_PARAMS, "utf8"),
    ) as Partial<FlowlabParams>;
    return normalizeParams(raw);
  } catch {
    return { ...DEFAULT_PARAMS };
  }
}

export function writeParams(params: Partial<FlowlabParams>): FlowlabParams {
  ensureFlowlabWorkspace();
  const next = normalizeParams(params);
  fs.writeFileSync(
    /*turbopackIgnore: true*/ FLOWLAB_PARAMS,
    JSON.stringify(next, null, 2) + "\n",
    "utf8",
  );
  return next;
}

export function sdcFileFor(preset: SdcPreset) {
  return SDC_MAP[preset];
}

/** Allowlisted make overrides for FlowLab (never free-form shell). */
export function makeOverridesFromParams(params: FlowlabParams): string[] {
  const p = normalizeParams(params);
  return [
    `FLOW_VARIANT=${FLOWLAB_VARIANT}`,
    `VERILOG_FILES=${FLOWLAB_RTL}`,
    `CORE_UTILIZATION=${p.coreUtilization}`,
    `PLACE_DENSITY_LB_ADDON=${p.placeDensityAddon}`,
    `ABC_AREA=${p.abcArea}`,
    `SDC_FILE=${sdcFileFor(p.sdcPreset)}`,
    `TNS_END_PERCENT=${p.tnsEndPercent}`,
  ];
}

export function flowlabResultsDir() {
  return path.join(
    /*turbopackIgnore: true*/ REPO_ROOT,
    `tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${FLOWLAB_VARIANT}`,
  );
}

export function flowlabSimArtifacts() {
  const simDir = path.join(/*turbopackIgnore: true*/ LEARN_ROOT, "sim/gcd");
  const logPath = path.join(simDir, "sim.log");
  const vcdPath = path.join(simDir, "gcd.vcd");
  return {
    logPath: "learn/sim/gcd/sim.log",
    vcdPath: "learn/sim/gcd/gcd.vcd",
    logExists: fs.existsSync(logPath),
    vcdExists: fs.existsSync(vcdPath),
    vcdBytes: fs.existsSync(vcdPath) ? fs.statSync(vcdPath).size : 0,
  };
}

export function flowlabPhaseHistory(limitPerPhase = 3) {
  const jobs = listJobs(80);
  const byAction = new Map<string, typeof jobs>();
  for (const ph of FLOW_PHASES) {
    byAction.set(
      ph.action,
      jobs.filter((j) => j.action === ph.action).slice(0, limitPerPhase),
    );
  }
  for (const extra of ["gridcheck", "activity_power", "klayout_drc", "system_pdn"]) {
    byAction.set(
      extra,
      jobs.filter((j) => j.action === extra).slice(0, limitPerPhase),
    );
  }
  return Object.fromEntries(byAction);
}

export function getFlowlabStatus() {
  ensureFlowlabWorkspace();
  const params = readParams();
  const rtl = readRtl();
  const resultsRoot = flowlabResultsDir();
  const stages = FLOW_PHASES.map((ph) => {
    if (ph.id === "rtl") {
      return {
        id: ph.id,
        label: ph.label,
        action: ph.action,
        ready: true,
        done: fs.existsSync(path.join(LEARN_ROOT, "sim/gcd/sim.log")),
      };
    }
    if (ph.id === "pdn") {
      const stamp = path.join(resultsRoot, ".gridcheck_pdn.ok");
      const odb = path.join(resultsRoot, "2_4_floorplan_pdn.odb");
      return {
        id: ph.id,
        label: ph.label,
        action: ph.action,
        ready: fs.existsSync(odb),
        done: fs.existsSync(stamp),
        primary: ".gridcheck_pdn.ok",
      };
    }
    if (ph.id === "pkg") {
      const stamp = path.join(resultsRoot, ".system_pdn.ok");
      const odb = path.join(resultsRoot, "6_final.odb");
      return {
        id: ph.id,
        label: ph.label,
        action: ph.action,
        ready: fs.existsSync(odb),
        done: fs.existsSync(stamp),
        primary: ".system_pdn.ok",
      };
    }
    const primary =
      ph.id === "synth"
        ? "1_synth.odb"
        : ph.id === "floorplan"
          ? "2_floorplan.odb"
          : ph.id === "place"
            ? "3_place.odb"
            : ph.id === "cts"
              ? "4_cts.odb"
              : ph.id === "route"
                ? "5_route.odb"
                : "6_final.gds";
    const exists = fs.existsSync(path.join(resultsRoot, primary));
    return {
      id: ph.id,
      label: ph.label,
      action: ph.action,
      ready: true,
      done: exists,
      primary,
    };
  });
  return {
    variant: FLOWLAB_VARIANT,
    rtlPath: "learn/flowlab/gcd.v",
    rtlBytes: Buffer.byteLength(rtl, "utf8"),
    rtlLines: rtl.split("\n").length,
    params,
    stages,
    sim: flowlabSimArtifacts(),
    phaseHistory: flowlabPhaseHistory(),
    resultsDir: `results/nangate45/gcd/${FLOWLAB_VARIANT}`,
  };
}

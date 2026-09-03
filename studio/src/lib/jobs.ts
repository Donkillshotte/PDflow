import { LONG_ACTIONS } from "./actions";
import fs from "fs";
import path from "path";
import { LEARN_ROOT, REPO_ROOT } from "./course";
import { collectStageResults } from "./results";
import { resultsDir } from "./open";

export { LONG_ACTIONS };

export const PIPELINE_STAGES = [
  "synth",
  "floorplan",
  "place",
  "cts",
  "route",
  "finish",
] as const;

export type PipelineStage = (typeof PIPELINE_STAGES)[number];

/** Prerequisite stage that must have key artifacts before running `stage`. */
export const STAGE_DEPS: Record<string, PipelineStage | null> = {
  check: null,
  status: null,
  list: null,
  test_course: null,
  rtl_sim: null,
  gate_sim: "finish",
  gridcheck: "floorplan",
  system_pdn: "finish",
  chip_pdn_ir: "finish",
  vyges_em_ir: "finish",
  dynamic_ir: "finish",
  power_chain: "finish",
  activity_power: "finish",
  vectorless: "finish",
  export_spice_lab: "finish",
  klayout_drc: "finish",
  sta_signoff: "finish",
  sta_ir_aware: "finish",
  drc_signoff: "finish",
  klayout_lvs: "finish",
  power_signoff: "finish",
  signoff_all: "finish",
  thermal_signoff: "finish",
  pkg_bump: "finish",
  pkg_rdl: "finish",
  pkg_signoff: "finish",
  signoff_phase2: "finish",
  yosys_equiv: null,
  formal_gcd: null,
  openrcx_report: "finish",
  analytical_pex: null,
  ccs_char: null,
  lvs_deep: "finish",
  layout_tools: null,
  spice_engines: null,
  tool_matrix: null,
  dse: null,
  synth: null,
  floorplan: "synth",
  place: "floorplan",
  cts: "place",
  route: "cts",
  finish: "route",
};

export type JobRecord = {
  id: string;
  action: string;
  command: string;
  status: "running" | "ok" | "error" | "cancelled";
  startedAt: string;
  finishedAt?: string;
  ms?: number;
  code?: number | null;
  logTail: string;
};

const HISTORY_PATH = () => path.join(LEARN_ROOT, ".studio-jobs.json");
const LOCK_PATH = () => path.join(LEARN_ROOT, ".studio-run.lock");
const MAX_HISTORY = 40;

type HistoryFile = { jobs: JobRecord[] };

function readHistory(): HistoryFile {
  try {
    if (!fs.existsSync(HISTORY_PATH())) return { jobs: [] };
    return JSON.parse(fs.readFileSync(HISTORY_PATH(), "utf8")) as HistoryFile;
  } catch {
    return { jobs: [] };
  }
}

function writeHistory(data: HistoryFile) {
  fs.mkdirSync(path.dirname(HISTORY_PATH()), { recursive: true });
  fs.writeFileSync(HISTORY_PATH(), JSON.stringify(data, null, 2) + "\n");
}

export function listJobs(limit = 20): JobRecord[] {
  return readHistory().jobs.slice(0, limit);
}

export function getJob(id: string): JobRecord | null {
  return readHistory().jobs.find((j) => j.id === id) ?? null;
}

export function upsertJob(job: JobRecord) {
  const data = readHistory();
  const idx = data.jobs.findIndex((j) => j.id === job.id);
  if (idx >= 0) data.jobs[idx] = job;
  else data.jobs.unshift(job);
  data.jobs = data.jobs.slice(0, MAX_HISTORY);
  writeHistory(data);
}

export function appendJobLog(id: string, chunk: string) {
  const data = readHistory();
  const job = data.jobs.find((j) => j.id === id);
  if (!job) return;
  job.logTail = (job.logTail + chunk).slice(-16000);
  writeHistory(data);
}

/** In-memory log buffer to avoid rewriting JSON on every chunk. */
const logBuffers = new Map<string, string>();

export function bufferJobLog(id: string, chunk: string) {
  const prev = logBuffers.get(id) ?? "";
  logBuffers.set(id, (prev + chunk).slice(-16000));
}

export function flushJobLog(id: string) {
  const buf = logBuffers.get(id);
  if (buf == null) return;
  const data = readHistory();
  const job = data.jobs.find((j) => j.id === id);
  if (job) {
    job.logTail = buf;
    writeHistory(data);
  }
}

export function clearJobLogBuffer(id: string) {
  logBuffers.delete(id);
}

export type LockInfo = {
  jobId: string;
  action: string;
  startedAt: string;
  pid?: number;
};

function pidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    // EPERM = process exists but we cannot signal it (e.g. pid 1)
    return Boolean(e && typeof e === "object" && "code" in e && e.code === "EPERM");
  }
}

export function readLock(): LockInfo | null {
  try {
    if (!fs.existsSync(LOCK_PATH())) return null;
    const lock = JSON.parse(fs.readFileSync(LOCK_PATH(), "utf8")) as LockInfo;
    if (lock.pid && !pidAlive(lock.pid)) {
      try {
        fs.unlinkSync(LOCK_PATH());
      } catch {
        /* ignore */
      }
      return null;
    }
    return lock;
  } catch {
    return null;
  }
}

export function acquireLock(
  info: LockInfo,
): { ok: true } | { ok: false; lock: LockInfo } {
  const existing = readLock();
  if (existing) return { ok: false, lock: existing };
  fs.mkdirSync(path.dirname(LOCK_PATH()), { recursive: true });
  fs.writeFileSync(LOCK_PATH(), JSON.stringify(info, null, 2) + "\n");
  return { ok: true };
}

export function releaseLock(jobId?: string) {
  const existing = readLock();
  if (!existing) return;
  if (jobId && existing.jobId !== jobId) return;
  try {
    fs.unlinkSync(LOCK_PATH());
  } catch {
    /* ignore */
  }
}

export function forceReleaseLock() {
  try {
    if (fs.existsSync(LOCK_PATH())) fs.unlinkSync(LOCK_PATH());
  } catch {
    /* ignore */
  }
}

export function stageReady(
  stage: string,
  variant = "learn",
): { ready: boolean; missing: string[]; dep: string | null } {
  const dep = STAGE_DEPS[stage] ?? null;
  if (!dep) return { ready: true, missing: [], dep: null };
  const results = collectStageResults(dep, variant);
  const missing = results.artifacts.filter((a) => !a.exists).map((a) => a.name);
  // Require the primary artifact (first listed — usually the stage .odb / GDS).
  const primary = results.artifacts[0];
  const ready = primary ? primary.exists : true;
  return { ready, missing, dep };
}

export type PipelineStatus = {
  stage: PipelineStage;
  ready: boolean;
  artifactCount: number;
  artifactReady: number;
  depsMet: boolean;
  dep: string | null;
  lastJob: JobRecord | null;
};

export function getPipelineStatus(): PipelineStatus[] {
  const jobs = listJobs(40);
  return PIPELINE_STAGES.map((stage) => {
    const r = collectStageResults(stage);
    const depInfo = stageReady(stage);
    const lastJob =
      jobs.find((j) => j.action === stage && j.status !== "running") ?? null;
    return {
      stage,
      ready: r.artifacts.some((a) => a.exists),
      artifactCount: r.artifacts.length,
      artifactReady: r.artifacts.filter((a) => a.exists).length,
      depsMet: depInfo.ready,
      dep: depInfo.dep,
      lastJob,
    };
  });
}

export type CompletionGate = {
  id: string;
  label: string;
  ok: boolean;
  detail?: string;
};

export { evaluateSignoffGates } from "./signoff";

export function evaluateLessonGates(input: {
  lessonId: string;
  makeTarget: string;
  steps: string[];
  checks: string[];
  checklistSize: number;
}): { ok: boolean; gates: CompletionGate[] } {
  const { makeTarget, steps, checks, checklistSize } = input;
  const theoryOk = steps.includes("theory");
  const labNeed =
    checklistSize === 0 ? 0 : Math.max(1, Math.ceil(checklistSize * 0.5));
  const labOk = checklistSize === 0 || checks.length >= labNeed;
  const runOk = steps.includes("run");
  const results = collectStageResults(makeTarget);
  const artifactsOk =
    results.artifacts.length === 0
      ? runOk
      : results.artifacts.some((a) => a.exists);

  const lastOkJob = listJobs(40).find(
    (j) => j.action === makeTarget && j.status === "ok",
  );
  const runGateOk = Boolean(lastOkJob) || (runOk && artifactsOk);
  const inspectOk = steps.includes("results");

  const gates: CompletionGate[] = [
    {
      id: "theory",
      label: "Theory reviewed",
      ok: theoryOk,
      detail: theoryOk
        ? "Theory step completed"
        : "open and confirm the Theory step",
    },
    {
      id: "lab",
      label: `LAB checklist (≥${labNeed})`,
      ok: labOk,
      detail: `${checks.length}/${checklistSize}`,
    },
    {
      id: "run",
      label: `Run ${makeTarget} succeeded`,
      ok: runGateOk,
      detail: lastOkJob
        ? `job ${lastOkJob.id.slice(0, 8)}… ok`
        : !runOk
          ? "complete the Run step with a successful run"
          : artifactsOk
            ? "artifacts present (previous run)"
            : "run the phase successfully",
    },
    {
      id: "artifacts",
      label: "Artifacts present",
      ok: artifactsOk,
      detail: `${results.artifacts.filter((a) => a.exists).length}/${results.artifacts.length}`,
    },
    {
      id: "results",
      label: "Results inspected",
      ok: inspectOk,
      detail: inspectOk
        ? "Results step completed"
        : "open the Results step",
    },
  ];

  return { ok: gates.every((g) => g.ok), gates };
}

export type PreflightResult =
  | { ok: true }
  | {
      ok: false;
      code: "locked" | "deps" | "forbidden";
      message: string;
      lock?: LockInfo;
      dep?: string | null;
      missing?: string[];
    };

export function preflightAction(
  action: string,
  opts: { variant?: string } = {},
): PreflightResult {
  const variant = opts.variant ?? "learn";
  // Artifact gates for extended / analysis actions
  const needFile: Record<string, { rel: string; hint: string }> = {
    gridcheck: {
      rel: "2_4_floorplan_pdn.odb",
      hint: "run floorplan first (PDN)",
    },
    activity_power: {
      rel: "6_final.odb",
      hint: "run finish first",
    },
    vectorless: {
      rel: "6_final.odb",
      hint: "run finish first (vectorless/dynamic)",
    },
    openrcx_report: {
      rel: "6_final.spef",
      hint: "run finish first (OpenRCX SPEF)",
    },
    chip_pdn_ir: {
      rel: "6_final.odb",
      hint: "run finish first (mesh SPICE)",
    },
    vyges_em_ir: {
      rel: "6_final.odb",
      hint: "run finish first (vyges-em-ir on PDN mesh)",
    },
    dynamic_ir: {
      rel: "6_final.odb",
      hint: "run finish first (dynamic IR I(t) on PDN mesh)",
    },
    power_chain: {
      rel: "6_final.odb",
      hint: "run finish first (full power chain)",
    },
    export_spice_lab: {
      rel: "6_final.odb",
      hint: "run finish first (export mesh SPICE)",
    },
    system_pdn: {
      rel: "6_final.odb",
      hint: "run finish first (I_die from activity/chip IR)",
    },
    klayout_drc: {
      rel: "6_final.gds",
      hint: "run finish first (GDS)",
    },
    sta_signoff: {
      rel: "6_final.v",
      hint: "run finish first (netlist SPEF)",
    },
    sta_ir_aware: {
      rel: "6_final.v",
      hint: "run finish + dynamic_ir first (STA arrivals × ITerm V)",
    },
    drc_signoff: {
      rel: "6_final.gds",
      hint: "run finish first (GDS DRC)",
    },
    klayout_lvs: {
      rel: "6_final.gds",
      hint: "run finish first (LVS GDS vs CDL)",
    },
    power_signoff: {
      rel: "6_final.odb",
      hint: "run finish first (power chain)",
    },
    signoff_all: {
      rel: "6_final.odb",
      hint: "run finish first (full signoff)",
    },
    thermal_signoff: {
      rel: "6_final.odb",
      hint: "run finish first (HotSpot °C + chip IR secondary)",
    },
    pkg_bump: {
      rel: "6_final.odb",
      hint: "run finish first (mesh SPICE bump)",
    },
    pkg_rdl: {
      rel: "6_final.odb",
      hint: "run finish first (sidecar rdl_route + dummy bump LEF)",
    },
    pkg_signoff: {
      rel: "6_final.odb",
      hint: "run finish first (PKG signoff)",
    },
    signoff_phase2: {
      rel: "6_final.odb",
      hint: "run finish first (signoff Phase 2 HotSpot + PKG)",
    },
    gate_sim: {
      rel: "6_final.v",
      hint: "run finish first (gate-level VCD)",
    },
    lvs_deep: {
      rel: "6_final.gds",
      hint: "run finish first (filtered LVS + VTL tolerances, no fake pass)",
    },
  };
  const need = needFile[action];
  if (need) {
    const abs = path.join(
      /*turbopackIgnore: true*/ resultsDir(variant),
      need.rel,
    );
    if (!fs.existsSync(abs)) {
      return {
        ok: false,
        code: "deps",
        message: `Missing artifact «${need.rel}»: ${need.hint}.`,
        missing: [need.rel],
      };
    }
  }
  if (action === "gate_sim") {
    const net = path.join(
      /*turbopackIgnore: true*/ resultsDir(variant),
      "6_final.v",
    );
    const cells = path.join(
      /*turbopackIgnore: true*/ LEARN_ROOT,
      "platforms/nangate45/verilog/NangateOpenCellLibrary.v",
    );
    const tb = path.join(
      /*turbopackIgnore: true*/ LEARN_ROOT,
      "sim/gcd/tb_gcd_gate.v",
    );
    if (!fs.existsSync(net) || !fs.existsSync(cells) || !fs.existsSync(tb)) {
      return {
        ok: false,
        code: "deps",
        message: "Missing gate netlist, Nangate .v, or gate testbench.",
        missing: ["6_final.v", "NangateOpenCellLibrary.v", "tb_gcd_gate.v"],
      };
    }
  }
  if (action === "rtl_sim") {
    const rtl =
      variant === "flowlab"
        ? path.join(/*turbopackIgnore: true*/ LEARN_ROOT, "flowlab/gcd.v")
        : path.join(
            /*turbopackIgnore: true*/ REPO_ROOT,
            "tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v",
          );
    const tb = path.join(
      /*turbopackIgnore: true*/ LEARN_ROOT,
      "sim/gcd/tb_gcd.v",
    );
    if (!fs.existsSync(rtl) || !fs.existsSync(tb)) {
      return {
        ok: false,
        code: "deps",
        message: "Missing RTL or GCD testbench.",
        missing: ["gcd.v", "tb_gcd.v"],
      };
    }
  }

  const dep = stageReady(action, variant);
  if (!dep.ready) {
    return {
      ok: false,
      code: "deps",
      message: `Missing dependency: run «${dep.dep}» first (missing artifacts: ${dep.missing.join(", ") || "all"}).`,
      dep: dep.dep,
      missing: dep.missing,
    };
  }
  const lock = readLock();
  if (lock) {
    return {
      ok: false,
      code: "locked",
      message: `A job is already running (${lock.action}, since ${lock.startedAt}).`,
      lock,
    };
  }
  return { ok: true };
}

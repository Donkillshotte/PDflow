import fs from "fs";
import path from "path";
import { LEARN_ROOT } from "./course";
import { collectStageResults } from "./results";

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
  synth: null,
  floorplan: "synth",
  place: "floorplan",
  cts: "place",
  route: "cts",
  finish: "route",
};

export const LONG_ACTIONS = new Set(["cts", "route", "finish", "test_course"]);

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
): { ready: boolean; missing: string[]; dep: string | null } {
  const dep = STAGE_DEPS[stage] ?? null;
  if (!dep) return { ready: true, missing: [], dep: null };
  const results = collectStageResults(dep);
  const missing = results.artifacts.filter((a) => !a.exists).map((a) => a.name);
  const ready =
    results.artifacts.length === 0
      ? true
      : results.artifacts.some((a) => a.exists);
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

export function evaluateLessonGates(input: {
  lessonId: string;
  makeTarget: string;
  steps: string[];
  checks: string[];
  checklistSize: number;
}): { ok: boolean; gates: CompletionGate[] } {
  const { makeTarget, steps, checks, checklistSize } = input;
  const theoryOk = steps.includes("teoria");
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
  const inspectOk = steps.includes("risultati");

  const gates: CompletionGate[] = [
    {
      id: "teoria",
      label: "Teoria consultata",
      ok: theoryOk,
      detail: theoryOk
        ? "passo Teoria completato"
        : "apri e conferma il passo Teoria",
    },
    {
      id: "lab",
      label: `LAB checklist (≥${labNeed})`,
      ok: labOk,
      detail: `${checks.length}/${checklistSize}`,
    },
    {
      id: "run",
      label: `Run ${makeTarget} riuscito`,
      ok: runGateOk,
      detail: lastOkJob
        ? `job ${lastOkJob.id.slice(0, 8)}… ok`
        : !runOk
          ? "completa il passo Esegui con un run riuscito"
          : artifactsOk
            ? "artefatti presenti (run precedente)"
            : "esegui la fase con successo",
    },
    {
      id: "artefatti",
      label: "Artefatti presenti",
      ok: artifactsOk,
      detail: `${results.artifacts.filter((a) => a.exists).length}/${results.artifacts.length}`,
    },
    {
      id: "risultati",
      label: "Risultati ispezionati",
      ok: inspectOk,
      detail: inspectOk
        ? "passo Risultati completato"
        : "apri il passo Risultati",
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

export function preflightAction(action: string): PreflightResult {
  const dep = stageReady(action);
  if (!dep.ready) {
    return {
      ok: false,
      code: "deps",
      message: `Dipendenza mancante: esegui prima «${dep.dep}» (artefatti assenti: ${dep.missing.join(", ") || "tutti"}).`,
      dep: dep.dep,
      missing: dep.missing,
    };
  }
  const lock = readLock();
  if (lock) {
    return {
      ok: false,
      code: "locked",
      message: `Un job è già in corso (${lock.action}, da ${lock.startedAt}).`,
      lock,
    };
  }
  return { ok: true };
}

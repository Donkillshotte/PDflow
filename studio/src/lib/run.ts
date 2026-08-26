import { ChildProcess, spawn } from "child_process";
import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";
import { SCRIPTS_ROOT, REPO_ROOT, LEARN_ROOT } from "./course";
import {
  acquireLock,
  bufferJobLog,
  clearJobLogBuffer,
  flushJobLog,
  getJob,
  preflightAction,
  releaseLock,
  upsertJob,
  type JobRecord,
} from "./jobs";

export type RunResult = {
  ok: boolean;
  code: number | null;
  stdout: string;
  stderr: string;
  command: string;
};

export type StreamEvent =
  | { type: "start"; jobId: string; command: string; action: string }
  | { type: "stdout"; chunk: string }
  | { type: "stderr"; chunk: string }
  | { type: "done"; ok: boolean; code: number | null; ms: number; status: JobRecord["status"] }
  | { type: "error"; message: string }
  | { type: "blocked"; code: "locked" | "deps" | "forbidden"; message: string; detail?: unknown };

const ALLOWED_ACTIONS = new Set([
  "check",
  "status",
  "list",
  "synth",
  "floorplan",
  "place",
  "cts",
  "route",
  "finish",
  "test_course",
]);

type Job = {
  id: string;
  child: ChildProcess;
  startedAt: number;
  cancelled: boolean;
};

const jobs = new Map<string, Job>();

export function isAllowedAction(action: string) {
  return ALLOWED_ACTIONS.has(action);
}

function truncate(s: string, max = 12000) {
  if (s.length <= max) return s;
  return s.slice(0, max) + "\n…[troncato]…\n";
}

function ensureTutorialSymlink() {
  const flow = path.join(REPO_ROOT, "tools/OpenROAD-flow-scripts/flow");
  const dest = path.join(flow, "designs/nangate45/gcd-tutorial");
  const src = path.join(LEARN_ROOT, "designs/nangate45/gcd-tutorial");
  if (!fs.existsSync(flow) || !fs.existsSync(src)) return;
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  try {
    const st = fs.lstatSync(dest);
    if (st.isSymbolicLink() || st.isDirectory() || st.isFile()) {
      fs.rmSync(dest, { recursive: true, force: true });
    }
  } catch {
    /* missing is fine */
  }
  fs.symlinkSync(src, dest);
}

function resolveCommand(action: string): {
  cmd: string;
  args: string[];
  cwd: string;
  command: string;
} {
  if (action === "test_course") {
    const cmd = path.join(SCRIPTS_ROOT, "test_course.sh");
    return { cmd, args: [], cwd: REPO_ROOT, command: cmd };
  }
  if (action === "check" || action === "status" || action === "list") {
    const cmd = path.join(SCRIPTS_ROOT, "learn_physical_design.sh");
    return {
      cmd,
      args: [`--${action}`],
      cwd: REPO_ROOT,
      command: `${cmd} --${action}`,
    };
  }
  ensureTutorialSymlink();
  const flow = path.join(REPO_ROOT, "tools/OpenROAD-flow-scripts/flow");
  return {
    cmd: "make",
    args: [
      "DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk",
      "FLOW_VARIANT=learn",
      "CORE_UTILIZATION=35",
      `OPENROAD_EXE=${process.env.OPENROAD_EXE || "openroad"}`,
      `OPENSTA_EXE=${process.env.OPENSTA_EXE || "sta"}`,
      `YOSYS_EXE=${process.env.YOSYS_EXE || "yosys"}`,
      action,
    ],
    cwd: flow,
    command: `make FLOW_VARIANT=learn CORE_UTILIZATION=35 ${action}`,
  };
}

function defaultTimeout(action: string) {
  return action === "finish" || action === "route" || action === "test_course"
    ? 900_000
    : 300_000;
}

export function cancelJob(jobId: string): boolean {
  const job = jobs.get(jobId);
  if (!job) return false;
  job.cancelled = true;
  try {
    job.child.kill("SIGTERM");
    setTimeout(() => {
      try {
        job.child.kill("SIGKILL");
      } catch {
        /* ignore */
      }
    }, 2000);
  } catch {
    return false;
  }
  return true;
}

export async function* streamCourseAction(
  action: string,
  opts: { timeoutMs?: number; signal?: AbortSignal; skipPreflight?: boolean } = {},
): AsyncGenerator<StreamEvent> {
  if (!isAllowedAction(action)) {
    yield {
      type: "blocked",
      code: "forbidden",
      message: `Azione non consentita: ${action}`,
    };
    return;
  }

  if (!opts.skipPreflight) {
    const pf = preflightAction(action);
    if (!pf.ok) {
      yield {
        type: "blocked",
        code: pf.code,
        message: pf.message,
        detail: pf,
      };
      return;
    }
  }

  const { cmd, args, cwd, command } = resolveCommand(action);
  const jobId = randomUUID();
  const startedAt = Date.now();
  const startedIso = new Date(startedAt).toISOString();
  const timeoutMs = opts.timeoutMs ?? defaultTimeout(action);

  const lock = acquireLock({
    jobId,
    action,
    startedAt: startedIso,
    pid: process.pid,
  });
  if (!lock.ok) {
    yield {
      type: "blocked",
      code: "locked",
      message: `Un job è già in corso (${lock.lock.action}).`,
      detail: lock.lock,
    };
    return;
  }

  const record: JobRecord = {
    id: jobId,
    action,
    command,
    status: "running",
    startedAt: startedIso,
    logTail: `$ ${command}\n`,
  };
  upsertJob(record);
  bufferJobLog(jobId, `$ ${command}\n`);

  const child = spawn(/*turbopackIgnore: true*/ cmd, args, {
    cwd,
    env: { ...process.env, LEARN_AUTO: "1", FORCE_COLOR: "0" },
  });
  jobs.set(jobId, { id: jobId, child, startedAt, cancelled: false });

  yield { type: "start", jobId, command, action };

  const queue: StreamEvent[] = [];
  let resolveWait: (() => void) | null = null;
  let closed = false;
  let exitCode: number | null = null;

  const wake = () => {
    if (resolveWait) {
      resolveWait();
      resolveWait = null;
    }
  };

  const push = (ev: StreamEvent) => {
    queue.push(ev);
    wake();
  };

  const onChunk = (stream: "stdout" | "stderr", chunk: string) => {
    bufferJobLog(jobId, chunk);
    push({ type: stream, chunk });
  };

  child.stdout.on("data", (d) => onChunk("stdout", d.toString()));
  child.stderr.on("data", (d) => onChunk("stderr", d.toString()));
  child.on("error", (err) => {
    bufferJobLog(jobId, `\n[error] ${err.message}\n`);
    push({ type: "error", message: err.message });
    closed = true;
    wake();
  });
  child.on("close", (code) => {
    exitCode = code;
    closed = true;
    wake();
  });

  const timer = setTimeout(() => {
    child.kill("SIGTERM");
    const msg = "\n[timeout] processo interrotto\n";
    bufferJobLog(jobId, msg);
    push({ type: "stderr", chunk: msg });
  }, timeoutMs);

  const onAbort = () => {
    const j = jobs.get(jobId);
    if (j) j.cancelled = true;
    child.kill("SIGTERM");
    const msg = "\n[annullato]\n";
    bufferJobLog(jobId, msg);
    push({ type: "stderr", chunk: msg });
  };
  opts.signal?.addEventListener("abort", onAbort);

  const flushTimer = setInterval(() => flushJobLog(jobId), 1500);

  try {
    while (!closed || queue.length > 0) {
      if (queue.length === 0) {
        await new Promise<void>((r) => {
          resolveWait = r;
        });
        continue;
      }
      yield queue.shift()!;
    }

    const ms = Date.now() - startedAt;
    const cancelled = jobs.get(jobId)?.cancelled ?? false;
    const status: JobRecord["status"] = cancelled
      ? "cancelled"
      : exitCode === 0
        ? "ok"
        : "error";
    flushJobLog(jobId);
    const existing = getJob(jobId);
    upsertJob({
      ...record,
      status,
      finishedAt: new Date().toISOString(),
      ms,
      code: exitCode,
      logTail: (existing?.logTail || record.logTail).slice(-16000),
    });

    yield {
      type: "done",
      ok: status === "ok",
      code: exitCode,
      ms,
      status,
    };
  } finally {
    clearInterval(flushTimer);
    flushJobLog(jobId);
    clearJobLogBuffer(jobId);
    clearTimeout(timer);
    opts.signal?.removeEventListener("abort", onAbort);
    jobs.delete(jobId);
    releaseLock(jobId);
  }
}

export function runCourseAction(
  action: string,
  opts: { timeoutMs?: number } = {},
): Promise<RunResult> {
  return new Promise(async (resolve) => {
    let stdout = "";
    let stderr = "";
    let command = "";
    let ok = false;
    let code: number | null = 1;
    try {
      for await (const ev of streamCourseAction(action, opts)) {
        if (ev.type === "start") command = ev.command;
        if (ev.type === "stdout") stdout += ev.chunk;
        if (ev.type === "stderr") stderr += ev.chunk;
        if (ev.type === "error") stderr += `\n${ev.message}`;
        if (ev.type === "blocked") stderr += `\n${ev.message}`;
        if (ev.type === "done") {
          ok = ev.ok;
          code = ev.code;
        }
      }
    } catch (e) {
      stderr += e instanceof Error ? e.message : String(e);
    }
    resolve({
      ok,
      code,
      stdout: truncate(stdout),
      stderr: truncate(stderr),
      command,
    });
  });
}

export type ToolStatus = {
  name: string;
  ok: boolean;
  detail: string;
};

export async function probeToolchain(): Promise<{
  tools: ToolStatus[];
  orfs: boolean;
  tutorial: boolean;
}> {
  const { execFile } = await import("child_process");
  const { promisify } = await import("util");
  const execFileAsync = promisify(execFile);

  async function ver(bin: string, args: string[]): Promise<ToolStatus> {
    try {
      const { stdout, stderr } = await execFileAsync(bin, args, { timeout: 8000 });
      const out = (stdout || stderr).trim().split("\n")[0] || "ok";
      return { name: bin, ok: true, detail: out.slice(0, 120) };
    } catch (e) {
      return {
        name: bin,
        ok: false,
        detail: e instanceof Error ? e.message : "mancante",
      };
    }
  }

  const tools = await Promise.all([
    ver("openroad", ["-version"]),
    ver("yosys", ["-V"]),
    ver("sta", ["-version"]),
    ver("klayout", ["-v"]),
  ]);

  return {
    tools,
    orfs: fs.existsSync(path.join(REPO_ROOT, "tools/OpenROAD-flow-scripts/flow")),
    tutorial: fs.existsSync(
      path.join(LEARN_ROOT, "designs/nangate45/gcd-tutorial/config.mk"),
    ),
  };
}

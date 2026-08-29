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
import { defaultActionTimeoutMs } from "./actions";
import {
  FLOWLAB_RTL,
  FLOWLAB_VARIANT,
  makeOverridesFromParams,
  normalizeParams,
  readParams,
  type FlowlabParams,
} from "./flowlab";

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
  | {
      type: "done";
      ok: boolean;
      code: number | null;
      ms: number;
      status: JobRecord["status"];
    }
  | { type: "error"; message: string }
  | {
      type: "blocked";
      code: "locked" | "deps" | "forbidden";
      message: string;
      detail?: unknown;
    };

export type RunMode = "learn" | "flowlab";

export type StreamOpts = {
  timeoutMs?: number;
  signal?: AbortSignal;
  skipPreflight?: boolean;
  mode?: RunMode;
  params?: Partial<FlowlabParams>;
};

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
  "rtl_sim",
  "gridcheck",
  "system_pdn",
  "chip_pdn_ir",
  "power_chain",
  "activity_power",
  "export_spice_lab",
  "klayout_drc",
  "sta_signoff",
  "drc_signoff",
  "klayout_lvs",
  "power_signoff",
  "signoff_all",
  "thermal_signoff",
  "pkg_bump",
  "pkg_rdl",
  "pkg_signoff",
  "signoff_phase2",
  "vectorless",
  "yosys_equiv",
  "formal_gcd",
  "openrcx_report",
  "analytical_pex",
  "layout_tools",
  "spice_engines",
  "vyges_em_ir",
  "tool_matrix",
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

function resolveCommand(
  action: string,
  opts: { mode?: RunMode; params?: Partial<FlowlabParams> } = {},
): {
  cmd: string;
  args: string[];
  cwd: string;
  command: string;
  env?: Record<string, string>;
} {
  const mode = opts.mode ?? "learn";
  const flowlab = mode === "flowlab";
  const params = normalizeParams(
    opts.params ?? (flowlab ? readParams() : {}),
  );

  if (action === "test_course") {
    const cmd = path.join(SCRIPTS_ROOT, "test_course.sh");
    return { cmd, args: [], cwd: REPO_ROOT, command: cmd };
  }
  if (action === "rtl_sim") {
    const cmd = path.join(LEARN_ROOT, "scripts/run_rtl_sim.sh");
    const env = flowlab ? { RTL_FILE: FLOWLAB_RTL } : undefined;
    return {
      cmd,
      args: [],
      cwd: REPO_ROOT,
      command: flowlab ? `RTL_FILE=learn/flowlab/gcd.v ${cmd}` : cmd,
      env,
    };
  }
  if (action === "gridcheck") {
    const cmd = path.join(LEARN_ROOT, "scripts/run_gridcheck.sh");
    const variant = flowlab ? FLOWLAB_VARIANT : "learn";
    return {
      cmd,
      args: ["pdn"],
      cwd: REPO_ROOT,
      command: `FLOW_VARIANT=${variant} ${cmd} pdn`,
      env: { FLOW_VARIANT: variant },
    };
  }
  if (action === "system_pdn") {
    const cmd = path.join(LEARN_ROOT, "scripts/run_system_pdn.sh");
    const variant = flowlab ? FLOWLAB_VARIANT : "learn";
    return {
      cmd,
      args: [],
      cwd: REPO_ROOT,
      command: `FLOW_VARIANT=${variant} ${cmd}`,
      env: {
        FLOW_VARIANT: variant,
        PYTHONPATH: `/usr/lib/python3/dist-packages${
          process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""
        }`,
      },
    };
  }
  if (action === "chip_pdn_ir") {
    const cmd = path.join(LEARN_ROOT, "scripts/run_chip_pdn_ir.sh");
    const variant = flowlab ? FLOWLAB_VARIANT : "learn";
    return {
      cmd,
      args: [],
      cwd: REPO_ROOT,
      command: `FLOW_VARIANT=${variant} ${cmd}`,
      env: {
        FLOW_VARIANT: variant,
        PYTHONPATH: `/usr/lib/python3/dist-packages${
          process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""
        }`,
      },
    };
  }
  if (action === "power_chain") {
    const cmd = path.join(LEARN_ROOT, "scripts/run_power_chain.sh");
    const variant = flowlab ? FLOWLAB_VARIANT : "learn";
    return {
      cmd,
      args: [],
      cwd: REPO_ROOT,
      command: `FLOW_VARIANT=${variant} ${cmd}`,
      env: {
        FLOW_VARIANT: variant,
        PYTHONPATH: `/usr/lib/python3/dist-packages${
          process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""
        }`,
      },
    };
  }
  if (action === "export_spice_lab") {
    const cmd = path.join(LEARN_ROOT, "scripts/export_spice_lab.sh");
    const variant = flowlab ? FLOWLAB_VARIANT : "learn";
    return {
      cmd,
      args: [],
      cwd: REPO_ROOT,
      command: `FLOW_VARIANT=${variant} ${cmd}`,
      env: { FLOW_VARIANT: variant },
    };
  }
  if (action === "activity_power") {
    const cmd = path.join(LEARN_ROOT, "scripts/run_activity_power.sh");
    const variant = flowlab ? FLOWLAB_VARIANT : "learn";
    return {
      cmd,
      args: [],
      cwd: REPO_ROOT,
      command: `FLOW_VARIANT=${variant} ${cmd}`,
      env: { FLOW_VARIANT: variant },
    };
  }
  const analysisScripts: Record<string, { script: string; pythonpath?: boolean }> = {
    vectorless: { script: "run_vectorless.sh", pythonpath: true },
    yosys_equiv: { script: "run_yosys_equiv.sh" },
    formal_gcd: { script: "run_formal_gcd.sh" },
    openrcx_report: { script: "run_openrcx_report.sh" },
    analytical_pex: { script: "run_analytical_pex.py", pythonpath: true },
    layout_tools: { script: "run_layout_tools_probe.sh" },
    spice_engines: { script: "run_spice_engines.sh" },
    vyges_em_ir: { script: "run_vyges_em_ir.sh", pythonpath: true },
    tool_matrix: { script: "run_tool_matrix.sh", pythonpath: true },
  };
  if (action in analysisScripts) {
    const spec = analysisScripts[action]!;
    const cmd = path.join(LEARN_ROOT, "scripts", spec.script);
    const variant = flowlab ? FLOWLAB_VARIANT : "learn";
    const env: Record<string, string> = { FLOW_VARIANT: variant };
    if (spec.pythonpath) {
      env.PYTHONPATH = `/usr/lib/python3/dist-packages${
        process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""
      }`;
    }
    const isPy = spec.script.endsWith(".py");
    const args = isPy ? [cmd] : [];
    const invoke = isPy ? `python3 ${cmd}` : cmd;
    return {
      cmd: isPy ? "python3" : cmd,
      args,
      cwd: REPO_ROOT,
      command: `FLOW_VARIANT=${variant} ${invoke}`,
      env,
    };
  }
  if (action === "klayout_drc") {
    const cmd = path.join(LEARN_ROOT, "scripts/run_klayout_drc.sh");
    const variant = flowlab ? FLOWLAB_VARIANT : "learn";
    return {
      cmd,
      args: [],
      cwd: REPO_ROOT,
      command: `FLOW_VARIANT=${variant} ${cmd}`,
      env: { FLOW_VARIANT: variant },
    };
  }
  const signoffScripts: Record<string, string> = {
    sta_signoff: "run_sta_signoff.sh",
    drc_signoff: "run_drc_signoff.sh",
    klayout_lvs: "run_klayout_lvs.sh",
    power_signoff: "run_power_signoff.sh",
    signoff_all: "run_signoff_all.sh",
    thermal_signoff: "run_thermal_signoff.sh",
    pkg_bump: "run_pkg_bump.sh",
    pkg_rdl: "run_pkg_rdl.sh",
    pkg_signoff: "run_pkg_signoff.sh",
    signoff_phase2: "run_signoff_phase2.sh",
  };
  if (action in signoffScripts) {
    const cmd = path.join(LEARN_ROOT, "scripts", signoffScripts[action]!);
    const variant = flowlab ? FLOWLAB_VARIANT : "learn";
    const env: Record<string, string> = { FLOW_VARIANT: variant };
    if (action === "power_signoff" || action === "signoff_all") {
      env.PYTHONPATH = `/usr/lib/python3/dist-packages${
        process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""
      }`;
    }
    return {
      cmd,
      args: [],
      cwd: REPO_ROOT,
      command: `FLOW_VARIANT=${variant} ${cmd}`,
      env,
    };
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
  const overrides = flowlab
    ? makeOverridesFromParams(params)
    : ["FLOW_VARIANT=learn", "CORE_UTILIZATION=35"];
  const args = [
    "DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk",
    ...overrides,
    `OPENROAD_EXE=${process.env.OPENROAD_EXE || "openroad"}`,
    `OPENSTA_EXE=${process.env.OPENSTA_EXE || "sta"}`,
    `YOSYS_EXE=${process.env.YOSYS_EXE || "yosys"}`,
    action,
  ];
  const variant = flowlab ? FLOWLAB_VARIANT : "learn";
  return {
    cmd: "make",
    args,
    cwd: flow,
    command: `make FLOW_VARIANT=${variant} CORE_UTILIZATION=${flowlab ? params.coreUtilization : 35} ${action}`,
  };
}

function defaultTimeout(action: string) {
  return defaultActionTimeoutMs(action);
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
  opts: StreamOpts = {},
): AsyncGenerator<StreamEvent> {
  if (!isAllowedAction(action)) {
    yield {
      type: "blocked",
      code: "forbidden",
      message: `Azione non consentita: ${action}`,
    };
    return;
  }

  const mode = opts.mode ?? "learn";
  const variant = mode === "flowlab" ? FLOWLAB_VARIANT : "learn";

  if (!opts.skipPreflight) {
    const pf = preflightAction(action, { variant });
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

  const { cmd, args, cwd, command, env } = resolveCommand(action, {
    mode,
    params: opts.params,
  });
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
    env: { ...process.env, LEARN_AUTO: "1", FORCE_COLOR: "0", ...(env ?? {}) },
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
  opts: { timeoutMs?: number; mode?: RunMode } = {},
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
  required?: boolean;
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
      const { stdout, stderr } = await execFileAsync(bin, args, {
        timeout: 8000,
      });
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
    ver("iverilog", ["-V"]),
    ver("ngspice", ["-v"]),
  ]);

  async function optional(bin: string, args: string[]): Promise<ToolStatus> {
    const t = await ver(bin, args);
    return { ...t, required: false };
  }

  async function present(bin: string): Promise<ToolStatus> {
    try {
      const { stdout } = await execFileAsync("which", [bin], { timeout: 3000 });
      return {
        name: bin,
        ok: true,
        detail: stdout.trim().split("\n")[0] || "ok",
        required: false,
      };
    } catch {
      if (bin === "vyges-em-ir") {
        const local = path.join(REPO_ROOT, "tools/vyges-em-ir/vyges-em-ir");
        if (fs.existsSync(local)) {
          return { name: bin, ok: true, detail: local, required: false };
        }
      }
      return { name: bin, ok: false, detail: "mancante", required: false };
    }
  }

  const extra = await Promise.all([
    optional("magic", ["--version"]),
    present("netgen"),
    optional("z3", ["--version"]),
    present("eqy"),
    present("sby"),
    present("xyce"),
    present("fastercap"),
    present("vyges-em-ir"),
  ]);

  return {
    tools: [...tools, ...extra],
    orfs: fs.existsSync(
      path.join(REPO_ROOT, "tools/OpenROAD-flow-scripts/flow"),
    ),
    tutorial: fs.existsSync(
      path.join(LEARN_ROOT, "designs/nangate45/gcd-tutorial/config.mk"),
    ),
  };
}

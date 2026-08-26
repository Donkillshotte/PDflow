import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import { SCRIPTS_ROOT, REPO_ROOT, LEARN_ROOT } from "./course";

export type RunResult = {
  ok: boolean;
  code: number | null;
  stdout: string;
  stderr: string;
  command: string;
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
]);

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

function spawnResult(
  cmd: string,
  args: string[],
  cwd: string,
  command: string,
  timeoutMs: number,
): Promise<RunResult> {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, {
      cwd,
      env: { ...process.env, LEARN_AUTO: "1", FORCE_COLOR: "0" },
    });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      stderr += "\n[timeout] processo interrotto\n";
    }, timeoutMs);
    child.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      resolve({
        ok: false,
        code: 1,
        stdout: truncate(stdout),
        stderr: truncate(`${stderr}\n${err.message}`),
        command,
      });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({
        ok: code === 0,
        code,
        stdout: truncate(stdout),
        stderr: truncate(stderr),
        command,
      });
    });
  });
}

export function runCourseAction(
  action: string,
  opts: { timeoutMs?: number } = {},
): Promise<RunResult> {
  if (!isAllowedAction(action)) {
    return Promise.resolve({
      ok: false,
      code: 1,
      stdout: "",
      stderr: `Azione non consentita: ${action}`,
      command: "",
    });
  }

  const timeoutMs =
    opts.timeoutMs ??
    (action === "finish" || action === "route" || action === "test_course"
      ? 900_000
      : 300_000);

  if (action === "test_course") {
    const cmd = path.join(SCRIPTS_ROOT, "test_course.sh");
    return spawnResult(cmd, [], REPO_ROOT, cmd, timeoutMs);
  }

  if (action === "check" || action === "status" || action === "list") {
    const cmd = path.join(SCRIPTS_ROOT, "learn_physical_design.sh");
    return spawnResult(cmd, [`--${action}`], REPO_ROOT, `${cmd} --${action}`, timeoutMs);
  }

  ensureTutorialSymlink();
  const flow = path.join(REPO_ROOT, "tools/OpenROAD-flow-scripts/flow");
  const args = [
    "DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk",
    "FLOW_VARIANT=learn",
    "CORE_UTILIZATION=35",
    `OPENROAD_EXE=${process.env.OPENROAD_EXE || "openroad"}`,
    `OPENSTA_EXE=${process.env.OPENSTA_EXE || "sta"}`,
    `YOSYS_EXE=${process.env.YOSYS_EXE || "yosys"}`,
    action,
  ];
  return spawnResult(
    "make",
    args,
    flow,
    `make FLOW_VARIANT=learn ${action}`,
    timeoutMs,
  );
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

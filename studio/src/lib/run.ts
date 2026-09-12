import fs from "fs";
import path from "path";
import { LEARN_ROOT, REPO_ROOT } from "./course";
import { FLOWLAB_VARIANT, type FlowlabParams } from "./flowlab";
import { LONG_ACTIONS } from "./actions";
import {
  agentCommandText,
  cancelAgentJob,
  submitAgentAction,
  waitForAgentJob,
} from "./agentRun";
import { agentFetch } from "./agentClient";
import { discoverStudioTools } from "./pdflowRegistry";

/**
 * Browser/dev compatibility surface for the original Studio run helpers.
 *
 * All execution now goes through `agentRun` and the authenticated local
 * agent. This module intentionally contains no child-process, timeout, lock,
 * or report implementation. Keeping the old exports avoids breaking older
 * pages while making the safe execution boundary impossible to bypass from
 * Next route code.
 */

export { LONG_ACTIONS };

export type RunMode = "learn" | "flowlab";

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
      status: string;
    }
  | { type: "error"; message: string }
  | {
      type: "blocked";
      code: "locked" | "deps" | "forbidden";
      message: string;
      detail?: unknown;
    };

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
  "gate_sim",
  "gridcheck",
  "system_pdn",
  "chip_pdn_ir",
  "power_grid_em",
  "power_chain",
  "activity_power",
  "export_spice_lab",
  "klayout_drc",
  "sta_signoff",
  "sta_ir_aware",
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
  "ccs_char",
  "lab_asap7_pdk",
  "lab_asap7_pkg",
  "lab_asap7_chip_pdn",
  "lvs_deep",
  "layout_tools",
  "spice_engines",
  "vyges_em_ir",
  "dynamic_ir",
  "tool_matrix",
  "dse",
  "eco",
  "eco_apply",
  "eco_close",
  "inspect_stage",
]);

export function isAllowedAction(action: string): boolean {
  return ALLOWED_ACTIONS.has(action);
}

function bodyMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const record = body as { error?: unknown; reason?: unknown };
    const value = record.error ?? record.reason;
    if (typeof value === "string" && value.trim()) return value;
  }
  return fallback;
}

/**
 * Legacy async-generator facade. It keeps the old event shape for pages that
 * still consume `/api/run/stream`, but the job lifecycle is entirely owned by
 * the agent and its cgroup executor.
 */
export async function* streamCourseAction(
  action: string,
  opts: StreamOpts = {},
): AsyncGenerator<StreamEvent> {
  if (!isAllowedAction(action)) {
    yield {
      type: "blocked",
      code: "forbidden",
      message: `Action not allowed: ${action}`,
    };
    return;
  }

  const mode = opts.mode ?? "learn";
  const variant = mode === "flowlab" ? FLOWLAB_VARIANT : "learn";
  const submit = await submitAgentAction({
    action,
    variant,
    mode: "view",
    parameters: opts.params
      ? (opts.params as Record<string, unknown>)
      : undefined,
  });

  if (!submit.response) {
    yield {
      type: "blocked",
      code: "deps",
      message: "PDflow local agent is not running",
    };
    return;
  }
  if (!submit.response.ok || !submit.job) {
    yield {
      type: "blocked",
      code: "deps",
      message: bodyMessage(
        submit.body,
        "PDflow local agent rejected the action",
      ),
      detail: submit.body,
    };
    return;
  }
  if (submit.job.state === "GAP") {
    yield {
      type: "blocked",
      code: "deps",
      message: submit.job.reason || "PDflow action is not currently verifiable",
      detail: submit.job,
    };
    return;
  }

  const startedAt = Date.now();
  yield {
    type: "start",
    jobId: submit.job.job_id,
    command: agentCommandText(submit.job),
    action,
  };

  let latestLog = submit.job.log_tail || "";
  const finalJob = await waitForAgentJob(submit.job, {
    signal: opts.signal,
    onUpdate: (job) => {
      latestLog = job.log_tail || latestLog;
    },
  });
  if (latestLog) yield { type: "stdout", chunk: latestLog };
  const ok = finalJob.state === "COMPLETED" && finalJob.report?.ok === true;
  yield {
    type: "done",
    ok,
    code: finalJob.code ?? null,
    ms: Date.now() - startedAt,
    status:
      finalJob.state === "CANCELLED"
        ? "cancelled"
        : ok
          ? "ok"
          : "error",
  };
}

export async function runCourseAction(
  action: string,
  opts: { timeoutMs?: number; mode?: RunMode } = {},
): Promise<RunResult> {
  let stdout = "";
  let stderr = "";
  let command = "";
  let ok = false;
  let code: number | null = 1;
  try {
    for await (const event of streamCourseAction(action, opts)) {
      if (event.type === "start") command = event.command;
      if (event.type === "stdout") stdout += event.chunk;
      if (event.type === "stderr") stderr += event.chunk;
      if (event.type === "error" || event.type === "blocked") {
        stderr += `\n${event.message}`;
      }
      if (event.type === "done") {
        ok = event.ok;
        code = event.code;
      }
    }
  } catch (error) {
    stderr += `\n${error instanceof Error ? error.message : String(error)}`;
  }
  return {
    ok,
    code,
    stdout: stdout.slice(-16000),
    stderr: stderr.slice(-16000),
    command,
  };
}

/** Safe compatibility cancellation; the agent remains the process owner. */
export async function cancelJob(jobId: string): Promise<boolean> {
  return Boolean(await cancelAgentJob(jobId));
}

export type ToolStatus = {
  name: string;
  ok: boolean;
  detail: string;
  required?: boolean;
};

type RegistryTool = {
  tool_id?: string;
  required?: boolean;
  availability?: string;
  executable?: string | null;
  version?: string | null;
};

type ToolRegistry = {
  tools?: RegistryTool[];
};

/**
 * Read-only toolchain compatibility response backed by the agent registry.
 * The fallback only inspects the manifest and executable permissions; it
 * never starts version-probe processes from the Next server.
 */
export async function probeToolchain(): Promise<{
  tools: ToolStatus[];
  orfs: boolean;
  tutorial: boolean;
}> {
  const remote = await agentFetch<ToolRegistry>("/v1/registry");
  const registry = remote || discoverStudioTools();
  const tools = (registry.tools || []).map((tool) => {
    const name = tool.tool_id === "opensta" ? "sta" : tool.tool_id || "tool";
    const ready = tool.availability === "READY";
    return {
      name,
      ok: ready,
      detail:
        tool.version ||
        (ready ? tool.executable || "ready" : `${tool.availability || "missing"}`),
      required: tool.required !== false,
    } satisfies ToolStatus;
  });
  return {
    tools,
    orfs: fs.existsSync(path.join(REPO_ROOT, "tools/OpenROAD-flow-scripts/flow")),
    tutorial: fs.existsSync(
      path.join(LEARN_ROOT, "designs/nangate45/gcd-tutorial/config.mk"),
    ),
  };
}

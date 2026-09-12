import { isAllowedAction, type RunMode } from "@/lib/run";
import { preflightAction } from "@/lib/jobs";
import { FLOWLAB_VARIANT, normalizeParams, readParams } from "@/lib/flowlab";
import { authorizeRunRequest } from "@/lib/runAuth";
import {
  AgentUnavailableError,
  agentCommandText,
  appendAgentLogTail,
  cancelAgentJob,
  submitAgentAction,
  waitForAgentJob,
} from "@/lib/agentRun";

export const dynamic = "force-dynamic";
export const maxDuration = 900;

function jsonObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

const FLOWLAB_STAGE_ACTIONS = new Set([
  "synth",
  "floorplan",
  "place",
  "cts",
  "route",
  "finish",
]);

/**
 * Query parameters on this compatibility endpoint are intentionally split by
 * adapter.  FlowLab tuning knobs belong only to stage recooks; passing the
 * saved FlowLab object to a read-only analysis used to make valid requests
 * fail with errors such as "unsupported analysis parameter: abcArea".  The
 * native `/api/jobs` path already receives typed objects from the UI, while
 * this route remains a backwards-compatible URL facade for scripts and old
 * browser links.
 */
const ANALYSIS_QUERY_KEYS: Record<string, readonly string[]> = {
  gridcheck: ["checkpoint", "net", "require_terminals"],
  // `mode=flowlab` is the transport selector for this legacy route. Use an
  // explicit alias for the adapter's setup/hold mode to avoid confusing the
  // two namespaces.
  sta_checkpoint: ["checkpoint", "sta_mode", "max_paths"],
  chip_pdn_ir: [
    "checkpoint",
    "package_resistance",
    "package_inductance",
    "c_decap",
    "peak_factor",
  ],
  dynamic_ir: [
    "checkpoint",
    "package_resistance",
    "package_inductance",
    "c_decap",
    "peak_factor",
    "analysis_mode",
    "period_ns",
    "duration_ns",
    "timestep_ps",
  ],
  power_grid_em: [
    "checkpoint",
    "peak_factor",
    "ir_limit_pct",
    "c_decap",
    "switch_t_ns",
    "switch_dur_ns",
    "package_resistance",
  ],
  system_pdn: [
    "checkpoint",
    "die_current_ma",
    "peak_factor",
    "board_l_nh",
    "package_r_mohm",
    "package_l_nh",
    "board_bulk_uf",
    "package_c_pf",
    "target_z_mohm",
    "edge_ns",
    "delay_ns",
    "pulse_width_ns",
  ],
};

const NUMERIC_ANALYSIS_QUERY_KEYS = new Set([
  "max_paths",
  "package_resistance",
  "package_inductance",
  "c_decap",
  "peak_factor",
  "period_ns",
  "duration_ns",
  "timestep_ps",
  "ir_limit_pct",
  "switch_t_ns",
  "switch_dur_ns",
  "die_current_ma",
  "board_l_nh",
  "package_r_mohm",
  "package_l_nh",
  "board_bulk_uf",
  "package_c_pf",
  "target_z_mohm",
  "edge_ns",
  "delay_ns",
  "pulse_width_ns",
]);

function queryParameterValue(key: string, value: string): unknown {
  if (key === "require_terminals") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true" || normalized === "1") return true;
    if (normalized === "false" || normalized === "0") return false;
    // Let the agent return its typed validation error for malformed values.
    return value;
  }
  if (NUMERIC_ANALYSIS_QUERY_KEYS.has(key)) return Number(value);
  return value;
}

function actionParameterKey(queryKey: string): string {
  if (queryKey === "sta_mode" || queryKey === "analysis_mode") return "mode";
  return queryKey;
}

function requestParametersFor(
  action: string,
  mode: RunMode,
  url: URL,
): Record<string, unknown> | undefined {
  if (mode !== "flowlab") return undefined;

  if (FLOWLAB_STAGE_ACTIONS.has(action)) {
    return normalizeParams({
      ...readParams(),
      ...(url.searchParams.has("coreUtilization")
        ? { coreUtilization: Number(url.searchParams.get("coreUtilization")) }
        : {}),
      ...(url.searchParams.has("placeDensityAddon")
        ? { placeDensityAddon: Number(url.searchParams.get("placeDensityAddon")) }
        : {}),
      ...(url.searchParams.has("abcArea")
        ? { abcArea: Number(url.searchParams.get("abcArea")) as 0 | 1 }
        : {}),
      ...(url.searchParams.has("sdcPreset")
        ? {
            sdcPreset: url.searchParams.get("sdcPreset") as
              | "default"
              | "relaxed"
              | "tight",
          }
        : {}),
      ...(url.searchParams.has("tnsEndPercent")
        ? { tnsEndPercent: Number(url.searchParams.get("tnsEndPercent")) }
        : {}),
    }) as unknown as Record<string, unknown>;
  }

  const keys = ANALYSIS_QUERY_KEYS[action];
  if (!keys) return undefined;
  const parameters: Record<string, unknown> = {};
  for (const queryKey of keys) {
    const value = url.searchParams.get(queryKey);
    if (value !== null) {
      const actionKey = actionParameterKey(queryKey);
      parameters[actionKey] = queryParameterValue(actionKey, value);
    }
  }
  return Object.keys(parameters).length > 0 ? parameters : undefined;
}

export async function GET(req: Request) {
  const denied = authorizeRunRequest(req);
  if (denied) {
    return denied;
  }

  const url = new URL(req.url);
  const action = url.searchParams.get("action") ?? "";
  if (!isAllowedAction(action)) {
    return Response.json(
      { error: `Action not allowed: ${action}`, code: "forbidden" },
      { status: 400 },
    );
  }

  const mode = (url.searchParams.get("mode") === "flowlab"
    ? "flowlab"
    : "learn") as RunMode;
  const variant =
    action === "eco_apply"
      ? "flowlab"
      : action === "eco_close"
        ? "eco_scratch"
        : mode === "flowlab"
          ? FLOWLAB_VARIANT
          : "learn";

  // Keep the legacy URL facade typed per action.  In particular, never pass
  // saved FlowLab recook knobs (abcArea, density, SDC, …) into analysis
  // adapters that deliberately reject unknown parameters.
  const qParams = requestParametersFor(action, mode, url);

  const pf = preflightAction(action, { variant });
  if (!pf.ok) {
    return Response.json(
      {
        status: "GAP",
        ok: false,
        error: pf.message,
        code: pf.code,
        lock: "lock" in pf ? pf.lock : undefined,
        dep: "dep" in pf ? pf.dep : undefined,
        missing: "missing" in pf ? pf.missing : undefined,
      },
      {
        status:
          pf.code === "locked" ? 409 : pf.code === "forbidden" ? 403 : 412,
      },
    );
  }

  // `run_id` is a reporting context.  A candidate run is the only context
  // that may request edit mode through this compatibility endpoint.
  const runId = url.searchParams.get("run_id") || undefined;
  const candidateRunId = url.searchParams.get("candidate_run_id") || undefined;
  const submit = await submitAgentAction({
    action,
    variant,
    mode: candidateRunId ? "edit" : "view",
    runId,
    candidateRunId,
    parameters: qParams,
  });

  if (!submit.response) {
    return Response.json(
      {
        status: "GAP",
        ok: false,
        error: "PDflow local agent is not running",
        code: "agent_offline",
      },
      { status: 503 },
    );
  }
  if (!submit.response.ok) {
    const body = jsonObject(submit.body);
    return Response.json(
      Object.keys(body).length > 0
        ? body
        : {
            status: "GAP",
            ok: false,
            error: "PDflow local agent rejected the action",
          },
      { status: submit.response.status },
    );
  }
  if (!submit.job) {
    return Response.json(
      {
        status: "GAP",
        ok: false,
        error: "PDflow local agent returned an invalid job record",
        code: "agent_protocol",
      },
      { status: 502 },
    );
  }

  // Dependency/resource gaps are terminal records returned with HTTP 202 by
  // the agent.  Preserve the compatibility route's explicit precondition
  // failure instead of opening an SSE stream that can never run.
  if (submit.job.state === "GAP") {
    return Response.json(submit.job, { status: 412 });
  }

  const encoder = new TextEncoder();
  const agentJob = submit.job;
  let streamCancelled = false;
  let cancelRequested = false;
  const requestCancel = () => {
    if (cancelRequested) return;
    cancelRequested = true;
    void cancelAgentJob(agentJob.job_id);
  };
  const stream = new ReadableStream({
    async start(controller) {
      const send = (obj: unknown) => {
        if (streamCancelled) return;
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
      };
      let previousTail = agentJob.log_tail || "";
      let previousState = agentJob.state;
      let previousReason = agentJob.reason || agentJob.report?.reason || null;
      let previousReportStatus = agentJob.report?.status || null;
      const startedAt = Date.now();
      const onUpdate = (job: typeof agentJob) => {
        const chunk = appendAgentLogTail(previousTail, job.log_tail || "");
        previousTail = job.log_tail || "";
        if (chunk) send({ type: "stdout", chunk });
        const reason = job.reason || job.report?.reason || null;
        const reportStatus = job.report?.status || null;
        if (
          job.state !== previousState ||
          reason !== previousReason ||
          reportStatus !== previousReportStatus
        ) {
          send({
            type: "progress",
            state: job.state,
            reason,
            reportStatus,
            resource: job.resource || null,
          });
          previousState = job.state;
          previousReason = reason;
          previousReportStatus = reportStatus;
        }
      };
      try {
        send({
          type: "start",
          jobId: agentJob.job_id,
          command: agentCommandText(agentJob),
          action,
        });
        const finalJob = await waitForAgentJob(agentJob, {
          signal: req.signal,
          onUpdate,
        });
        const finalOk =
          finalJob.state === "COMPLETED" && finalJob.report?.ok === true;
        const status =
          finalJob.state === "CANCELLED"
            ? "cancelled"
            : finalOk
              ? "ok"
              : "error";
        send({
          type: "done",
          ok: finalOk,
          code: finalJob.code ?? null,
          ms: Date.now() - startedAt,
          status,
          state: finalJob.state,
          reason: finalJob.reason || finalJob.report?.reason || null,
          reportStatus: finalJob.report?.status || null,
          terminationCause: finalJob.termination_cause || null,
          resource: finalJob.resource || null,
        });
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          requestCancel();
        } else if (error instanceof AgentUnavailableError) {
          send({
            type: "error",
            message:
              error.message +
              "; the agent-owned job remains inspectable in the Jobs view",
          });
        } else {
          send({
            type: "error",
            message: error instanceof Error ? error.message : String(error),
          });
        }
      } finally {
        if (!streamCancelled) controller.close();
      }
    },
    cancel() {
      streamCancelled = true;
      requestCancel();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

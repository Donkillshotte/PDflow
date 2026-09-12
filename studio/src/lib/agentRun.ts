import { agentFetch, agentResponse } from "./agentClient";

/**
 * Compatibility helpers for the browser-facing run routes.
 *
 * The local agent is the only process owner.  These helpers deliberately
 * contain no child-process, timeout, lock, or log-file implementation; they
 * only submit a typed request and observe the agent-owned job record.
 */

export type AgentJob = {
  job_id: string;
  tool_id?: string;
  action?: string | null;
  operation?: string;
  state: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  run_id?: string | null;
  mode?: "view" | "edit";
  command?: string[];
  timeout_seconds?: number;
  code?: number | null;
  reason?: string | null;
  termination_cause?: string | null;
  log_tail?: string;
  report?: {
    report_id?: string;
    status?: string;
    ok?: boolean;
    reason?: string | null;
    details?: unknown;
  };
  resource?: Record<string, unknown>;
};

export type AgentActionRequest = {
  action: string;
  variant: string;
  mode?: "view" | "edit";
  runId?: string;
  candidateRunId?: string;
  parameters?: Record<string, unknown>;
};

export type AgentSubmitResult = {
  response: Response | null;
  job: AgentJob | null;
  body: unknown;
};

const TERMINAL_STATES = new Set([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "GAP",
  "ORPHANED",
]);

const POLL_INTERVAL_MS = 450;
const MAX_MISSED_POLLS = 20;

function isAgentJob(value: unknown): value is AgentJob {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { job_id?: unknown }).job_id === "string" &&
    typeof (value as { state?: unknown }).state === "string"
  );
}

async function readJson(response: Response): Promise<unknown> {
  return response.json().catch(() => null);
}

export async function submitAgentAction(
  request: AgentActionRequest,
): Promise<AgentSubmitResult> {
  const payload: Record<string, unknown> = {
    action: request.action,
    operation: "action",
    variant: request.variant,
    mode: request.mode ?? "view",
  };
  if (request.runId) payload.run_id = request.runId;
  if (request.candidateRunId) payload.candidate_run_id = request.candidateRunId;
  if (request.parameters) payload.parameters = request.parameters;

  const response = await agentResponse("/v1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response) return { response: null, job: null, body: null };
  const body = await readJson(response);
  return {
    response,
    job: isAgentJob(body) ? body : null,
    body,
  };
}

export async function getAgentJob(jobId: string): Promise<AgentJob | null> {
  const job = await agentFetch<unknown>(
    "/v1/jobs?id=" + encodeURIComponent(jobId),
  );
  return isAgentJob(job) ? job : null;
}

export async function cancelAgentJob(jobId: string): Promise<AgentJob | null> {
  const response = await agentResponse(
    "/v1/jobs/" + encodeURIComponent(jobId) + "/cancel",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    },
  );
  if (!response) return null;
  const body = await readJson(response);
  return isAgentJob(body) ? body : null;
}

export function isAgentJobTerminal(job: AgentJob): boolean {
  return TERMINAL_STATES.has(job.state);
}

export function agentCommandText(job: AgentJob): string {
  return (job.command ?? []).join(" ");
}

/**
 * Return only the new part of a bounded agent log tail.  Once the tail rolls
 * over, use the longest suffix/prefix overlap instead of replaying 16 KiB on
 * every poll.  This keeps both the SSE response and the UI log state bounded.
 */
export function appendAgentLogTail(previous: string, current: string): string {
  if (!current || current === previous) return "";
  if (!previous || current.startsWith(previous)) {
    return current.slice(previous.length);
  }

  const maxOverlap = Math.min(8192, previous.length, current.length);
  for (let length = maxOverlap; length >= 32; length -= 1) {
    if (previous.endsWith(current.slice(0, length))) {
      return current.slice(length);
    }
  }
  return `\n[agent log tail refreshed]\n${current}`;
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("The operation was aborted", "AbortError"));
      return;
    }
    let settled = false;
    const onAbort = () => {
      if (settled) return;
      settled = true;
      globalThis.clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      reject(new DOMException("The operation was aborted", "AbortError"));
    };
    const timer = globalThis.setTimeout(() => {
      if (settled) return;
      settled = true;
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export class AgentUnavailableError extends Error {
  constructor(message = "PDflow local agent status is unavailable") {
    super(message);
    this.name = "AgentUnavailableError";
  }
}

/**
 * Observe an already-submitted job until the agent reports a terminal state.
 * A short observation outage is tolerated.  If the agent remains unavailable,
 * the caller gets an explicit error while the job itself remains agent-owned
 * and inspectable through `/api/jobs`.
 */
export async function waitForAgentJob(
  initial: AgentJob,
  options: {
    signal?: AbortSignal;
    onUpdate?: (job: AgentJob) => void;
  } = {},
): Promise<AgentJob> {
  let job = initial;
  let missedPolls = 0;
  options.onUpdate?.(job);

  while (!isAgentJobTerminal(job)) {
    await delay(POLL_INTERVAL_MS, options.signal);
    if (options.signal?.aborted) {
      await cancelAgentJob(job.job_id);
      throw new DOMException("The operation was aborted", "AbortError");
    }

    const next = await getAgentJob(job.job_id);
    if (!next) {
      missedPolls += 1;
      if (missedPolls >= MAX_MISSED_POLLS) {
        throw new AgentUnavailableError(
          `PDflow local agent did not return job ${job.job_id} status`,
        );
      }
      continue;
    }
    missedPolls = 0;
    job = next;
    options.onUpdate?.(job);
  }
  return job;
}

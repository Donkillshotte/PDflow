import fs from "fs";
import path from "path";
import { agentFetch, agentResponse } from "./agentClient";
import { REPO_ROOT } from "./course";
import { candidateResultsRoot } from "./candidateWorkspace";
import {
  preferredResultsVariant,
  resultsDir,
  STAGE_GUI_TARGETS,
} from "./open";
import {
  normalizeCandidateRunId,
  normalizeRelativeArtifact,
  normalizeResultsVariant,
} from "./pathGuard";

/**
 * Agent-owned OpenROAD web viewer compatibility adapter.
 *
 * The Next process never starts or kills OpenROAD. It resolves a catalog
 * artifact, submits an allowlisted `operation=web` job, and observes/cancels
 * that job through the local agent.
 */

const DEFAULT_PORT = Number(process.env.STUDIO_OR_WEB_PORT || 43190);

type ViewerJob = {
  job_id?: string;
  state?: string;
  reason?: string | null;
  pid?: number;
  web_port?: number;
  artifact?: { relative_path?: string } | null;
};

type ViewerState = {
  running: boolean;
  agent_managed: true;
  display?: string | null;
  state?: string;
  job_id?: string;
  pid?: number;
  port?: number;
  url?: string;
  artifact?: string | null;
  stage?: string | null;
  run_id?: string | null;
  started_at?: string;
  reason?: string | null;
};

function offlineState(): ViewerState {
  return {
    running: false,
    agent_managed: true,
    reason: "PDflow local agent is not running",
  };
}

export async function viewerStatus(): Promise<ViewerState> {
  const state = await agentFetch<ViewerState>("/v1/viewer");
  return state || offlineState();
}

async function resolveArtifactId(
  relativePath: string,
  variant: string,
  runId?: string | null,
): Promise<string | null> {
  const query = new URLSearchParams({ limit: "2000" });
  if (runId) {
    query.set("run_id", runId);
    query.set("authority", "candidate");
  } else {
    query.set("variant", variant);
    query.set("authority", "finish");
  }
  const catalog = await agentFetch<{
    artifacts?: Array<{ artifact_id?: string; relative_path?: string }>;
  }>("/v1/artifacts?" + query.toString());
  return (
    catalog?.artifacts?.find(
      (artifact) => artifact.artifact_id && artifact.relative_path === relativePath,
    )?.artifact_id || null
  );
}

export async function stopViewer(): Promise<{ ok: boolean; message: string }> {
  const current = await viewerStatus();
  if (!current.job_id) {
    return { ok: true, message: current.reason || "no active viewer" };
  }
  const response = await agentResponse(
    "/v1/jobs/" + encodeURIComponent(current.job_id) + "/cancel",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    },
  );
  if (!response) {
    return { ok: false, message: "PDflow local agent is not running" };
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    return { ok: false, message: body.error || "viewer cancellation failed" };
  }
  return { ok: true, message: `viewer cancellation requested (${current.job_id})` };
}

export async function startViewer(
  stage: string,
  variant: string = preferredResultsVariant(),
  opts?: { artifact?: string; runId?: string | null },
): Promise<{
  ok: boolean;
  message: string;
  url?: string;
  port?: number;
  artifact?: string;
  job?: ViewerJob;
}> {
  const stageItems = STAGE_GUI_TARGETS[stage] ?? [];
  const allowed = new Set(
    stageItems
      .filter((item) => item.kind === "openroad")
      .map((item) => item.artifact),
  );
  let artifact: string;
  try {
    artifact = normalizeRelativeArtifact(
      opts?.artifact || stageItems.find((item) => item.kind === "openroad")?.artifact || "",
    );
  } catch {
    return { ok: false, message: "invalid viewer artifact" };
  }
  if (!artifact || !allowed.has(artifact)) {
    return { ok: false, message: `artifact is not allowed for stage: ${stage}` };
  }

  let root: string;
  let normalizedVariant: string;
  try {
    normalizedVariant = normalizeResultsVariant(variant);
    root = opts?.runId
      ? candidateResultsRoot(normalizeCandidateRunId(opts.runId))
      : resultsDir(normalizedVariant);
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "invalid viewer context",
    };
  }
  const abs = path.join(root, artifact);
  if (!fs.existsSync(abs)) {
    return {
      ok: false,
      message: `Missing artifact: ${artifact} — run phase ${stage} first (${normalizedVariant})`,
    };
  }
  const relativePath = path.relative(REPO_ROOT, abs).split(path.sep).join("/");
  const artifactId = await resolveArtifactId(relativePath, normalizedVariant, opts?.runId);
  if (!artifactId) {
    return { ok: false, message: `artifact is not registered: ${relativePath}` };
  }

  const current = await viewerStatus();
  if (
    current.running &&
    current.artifact === relativePath &&
    (current.stage || null) === (stage || null) &&
    (current.run_id || null) === (opts?.runId || null)
  ) {
    return {
      ok: true,
      message: "viewer already active on this artifact",
      url: current.url,
      port: current.port,
      artifact,
      job: { job_id: current.job_id, state: current.state },
    };
  }
  if (current.job_id) await stopViewer();

  const response = await agentResponse("/v1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tool_id: "openroad",
      operation: "web",
      artifact_id: artifactId,
      mode: "view",
      run_id: opts?.runId || undefined,
      viewer_stage: stage,
      web_port: DEFAULT_PORT,
    }),
  });
  if (!response) return { ok: false, message: "PDflow local agent is not running" };
  const job = (await response.json().catch(() => ({}))) as ViewerJob;
  const ok = response.ok && job.state !== "GAP" && job.state !== "FAILED";
  if (!ok) {
    return {
      ok: false,
      message: job.reason || "OpenROAD web viewer could not be started",
      job,
    };
  }
  return {
    ok: true,
    message: `OpenROAD Web Viewer delegated to the local agent on ${artifact}`,
    url: `http://127.0.0.1:${DEFAULT_PORT}/`,
    port: DEFAULT_PORT,
    artifact,
    job,
  };
}

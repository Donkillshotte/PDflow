import { NextResponse } from "next/server";
import { agentFetch, agentResponse } from "@/lib/agentClient";
import { isStageInspect, type StageInspect } from "@/lib/inspect";
import { preferredResultsVariant } from "@/lib/open";
import { normalizeResultsVariant } from "@/lib/pathGuard";

export const dynamic = "force-dynamic";

const STAGES = new Set([
  "synth",
  "floorplan",
  "pdn",
  "place",
  "cts",
  "route",
  "finish",
]);

type RemoteJob = {
  job_id?: unknown;
  action?: unknown;
  state?: unknown;
  run_id?: unknown;
  created_at?: unknown;
  report?: {
    report_id?: unknown;
    status?: unknown;
    ok?: unknown;
    reason?: unknown;
    stale?: unknown;
    details?: unknown;
    input_artifacts?: unknown;
    input_artifact_refs?: unknown;
  };
};

type RemoteReport = {
  report_id?: unknown;
  status?: unknown;
  ok?: unknown;
  stale?: unknown;
  reason?: unknown;
  details?: unknown;
  [key: string]: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isRemoteJob(value: unknown): value is RemoteJob {
  return isRecord(value) && typeof value.job_id === "string";
}

function safeRunId(value: string): boolean {
  return /^[A-Za-z0-9_.-]{8,100}$/.test(value);
}

/**
 * Read an existing native inspection report without submitting a job.
 * Recalculate remains the only path that invokes /api/inspect.
 */
export async function GET(req: Request) {
  const params = new URL(req.url).searchParams;
  const stage = params.get("stage") || "synth";
  if (!STAGES.has(stage)) {
    return NextResponse.json({ status: "NOT_RUN", ok: false, reason: "invalid stage" }, { status: 400 });
  }

  let variant: string;
  try {
    variant = normalizeResultsVariant(params.get("variant") || preferredResultsVariant());
  } catch {
    return NextResponse.json({ status: "NOT_RUN", ok: false, reason: "invalid variant" }, { status: 400 });
  }

  const requestedRunId = params.get("run_id");
  if (requestedRunId && !safeRunId(requestedRunId)) {
    return NextResponse.json({ status: "NOT_RUN", ok: false, reason: "invalid run_id" }, { status: 400 });
  }
  const requestedArtifactId = params.get("artifact_id");
  if (requestedArtifactId && !safeRunId(requestedArtifactId)) {
    return NextResponse.json({ status: "NOT_RUN", ok: false, reason: "invalid artifact_id" }, { status: 400 });
  }

  const remote = await agentFetch<unknown>("/v1/jobs?limit=200");
  if (!isRecord(remote) || !Array.isArray(remote.jobs)) {
    return NextResponse.json(
      {
        schema_version: 1,
        status: "GAP",
        ok: false,
        inspection: null,
        report: null,
        reason: "inspection cache unavailable because the local agent is offline",
      },
      { status: 503 },
    );
  }

  const jobs = remote.jobs.filter(isRemoteJob);
  const matches = jobs
    .filter((job) => job.action === "inspect_stage")
    .filter((job) => !requestedRunId || job.run_id === requestedRunId)
    .filter((job) => {
      if (!requestedArtifactId) return true;
      const ids = Array.isArray(job.report?.input_artifacts)
        ? job.report.input_artifacts
        : [];
      const refs = Array.isArray(job.report?.input_artifact_refs)
        ? job.report.input_artifact_refs
        : [];
      return (
        ids.includes(requestedArtifactId) ||
        refs.some(
          (ref) => isRecord(ref) && ref.artifact_id === requestedArtifactId,
        )
      );
    })
    .filter((job) => {
      const details = job.report?.details;
      return (
        isStageInspect(details) &&
        details.stage === stage &&
        (details.variant || variant) === variant
      );
    })
    .sort((left, right) =>
      String(right.created_at || "").localeCompare(String(left.created_at || "")),
    );

  const selected = matches[0];
  if (!selected) {
    return NextResponse.json({
      schema_version: 1,
      status: "NOT_RUN",
      ok: false,
      inspection: null,
      report: null,
      stage,
      variant,
      run_id: requestedRunId || null,
      artifact_id: requestedArtifactId || null,
      reason: "no cached inspection snapshot exists for this phase and context",
    });
  }

  let report: RemoteReport | null = isRecord(selected.report)
    ? (selected.report as RemoteReport)
    : null;
  const reportId = typeof report?.report_id === "string" ? report.report_id : null;
  if (reportId) {
    const response = await agentResponse(
      "/v1/reports/" + encodeURIComponent(reportId),
    );
    if (response?.ok) {
      const fresh = await response.json().catch(() => null);
      if (isRecord(fresh)) report = fresh as RemoteReport;
    }
  }

  const details = report?.details;
  const reportStatus =
    typeof report?.status === "string" &&
    ["PASS", "FAIL", "WARN", "PARTIAL", "PROXY", "GAP", "NOT_RUN"].includes(
      report.status,
    )
      ? (report.status as StageInspect["status"])
      : isStageInspect(details)
        ? details.status
        : "NOT_RUN";
  const reportReason =
    typeof report?.reason === "string" ? report.reason : null;
  const stale = report?.stale === true;
  const selectedJobId = typeof selected.job_id === "string" ? selected.job_id : "";
  const inspection = isStageInspect(details)
    ? ({
        ...details,
        status: stale ? "GAP" : reportStatus,
        ok: stale ? false : details.ok,
        reason: reportReason || details.reason || null,
        job_id: selectedJobId,
        report_id: reportId || details.report_id,
      } satisfies StageInspect)
    : null;
  const status = stale ? "GAP" : reportStatus || inspection?.status || "NOT_RUN";

  return NextResponse.json({
    schema_version: 1,
    status,
    ok: status === "PASS" && inspection?.ok === true,
    inspection,
    report,
    job_id: selectedJobId,
    report_id: reportId,
    run_id: selected.run_id || null,
    artifact_id: requestedArtifactId || null,
    stage,
    variant,
    reason: stale
      ? reportReason || "inspection input changed; cached report is stale"
      : reportReason,
  });
}

import { NextResponse } from "next/server";
import path from "path";
import { agentFetch, agentResponse } from "@/lib/agentClient";
import { REPO_ROOT } from "@/lib/course";
import {
  listOpenTargets,
  resolveArtifactOpen,
  resolveOpenTarget,
} from "@/lib/open";
import { normalizeCandidateRunId, normalizeRelativeArtifact } from "@/lib/pathGuard";
import { startViewer } from "@/lib/webviewer";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(listOpenTargets());
}

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "external tool launch");
  if (denied) {
    return denied;
  }
  const tooLarge = rejectOversizedBody(req, 16 * 1024);
  if (tooLarge) {
    return tooLarge;
  }
  const body = (await req.json()) as {
    id?: string;
    artifact?: string;
    dryRun?: boolean;
    variant?: string;
    mode?: "view" | "edit";
    run_id?: string;
  };

  // Candidate artifacts are never resolved through the canonical results
  // directory. Resolve the run through the local agent catalog first, then
  // delegate the native launch with the verified artifact id.
  if (body.run_id && body.artifact) {
    let candidateRunId: string;
    let artifactName: string;
    try {
      candidateRunId = normalizeCandidateRunId(body.run_id);
      artifactName = normalizeRelativeArtifact(body.artifact);
    } catch (error) {
      return NextResponse.json(
        { ok: false, error: error instanceof Error ? error.message : "invalid candidate artifact" },
        { status: 400 },
      );
    }
    const catalog = await agentFetch<{
      artifacts?: Array<{
        artifact_id?: string;
        relative_path?: string;
        kind?: string;
      }>;
    }>(
      `/v1/artifacts?run_id=${encodeURIComponent(candidateRunId)}&authority=candidate&limit=2000`,
    );
    if (!catalog) {
      return NextResponse.json(
        { ok: false, state: "GAP", error: "PDflow local agent is not running" },
        { status: 503 },
      );
    }
    const candidate = catalog.artifacts?.find(
      (item) =>
        item.artifact_id &&
        item.relative_path &&
        path.posix.basename(item.relative_path) === artifactName &&
        item.relative_path.includes("/candidate/orfs/results/"),
    );
    if (!candidate?.artifact_id) {
      return NextResponse.json(
        { ok: false, state: "GAP", error: `candidate artifact not found: ${artifactName}` },
        { status: 404 },
      );
    }
    const tool_id = ["gds", "oas", "lyrdb"].includes(candidate.kind || "")
      ? "klayout"
      : "openroad";
    const delegated = await agentFetch<{
      job_id?: string;
      state?: string;
      reason?: string;
    }>("/v1/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool_id,
        operation: "gui",
        artifact_id: candidate.artifact_id,
        mode: body.mode || "view",
        run_id: candidateRunId,
      }),
    });
    if (!delegated) {
      return NextResponse.json(
        { ok: false, state: "GAP", error: "candidate native launch failed" },
        { status: 503 },
      );
    }
    const ok = delegated.state !== "GAP" && delegated.state !== "FAILED";
    return NextResponse.json(
      {
        ok,
        launched: ok,
        job: delegated,
        message: ok
          ? `${artifactName} delegated to PDflow local agent`
          : delegated.reason || `${artifactName} could not be opened`,
      },
      { status: ok ? 200 : 503 },
    );
  }

  let target = body.id ? resolveOpenTarget(body.id) : null;
  if (!target && body.artifact) {
    target = resolveArtifactOpen(
      body.artifact,
      body.variant ?? undefined,
    );
  }
  if (!target) {
    return NextResponse.json(
      { error: "target not found", ok: false },
      { status: 404 },
    );
  }

  // In-app navigation targets
  if (
    target.kind === "dashboard" ||
    target.kind === "gallery" ||
    target.kind === "doc" ||
    target.kind === "lesson" ||
    target.kind === "run"
  ) {
    return NextResponse.json({
      ok: true,
      launched: false,
      navigate: target.href,
      target,
      message: `Open ${target.label}`,
    });
  }

  if (target.kind === "webviewer") {
    if (body.dryRun) {
      return NextResponse.json({
        ok: target.exists,
        launched: false,
        target,
        message: target.exists
          ? "dry-run webviewer ok"
          : `Missing artifact: ${target.artifact}`,
      });
    }
    if (!target.exists || !target.stage) {
      return NextResponse.json(
        {
          ok: false,
          launched: false,
          message: `Missing ODB for web viewer (${target.stage ?? "?"})`,
          target,
        },
        { status: 412 },
      );
    }
    const started = await startViewer(target.stage, body.variant, {
      artifact: target.artifact,
      runId: body.run_id,
    });
    return NextResponse.json(
      {
        ...started,
        launched: Boolean(started.ok && started.url),
        navigate: target.href,
        url: started.url,
        target,
      },
      { status: started.ok ? 200 : 412 },
    );
  }

  if (body.dryRun) {
    return NextResponse.json({
      ok: target.exists,
      launched: false,
      target,
      command: target.command,
      message: target.exists
        ? "dry-run ok"
        : `Missing artifact: ${target.artifact}`,
    });
  }

  // All native processes belong to the local agent. The Next server only
  // submits a typed request and never owns a child process.
  if (
    (target.kind === "openroad" || target.kind === "klayout") &&
    target.absPath
  ) {
    const artifactPath = path
      .relative(REPO_ROOT, target.absPath)
      .split(path.sep)
      .join("/");
    const response = await agentResponse("/v1/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool_id: target.kind,
        operation: "gui",
        artifact_path: artifactPath,
        mode: body.mode || "view",
        run_id: body.run_id,
      }),
    });
    if (response) {
      const delegated = (await response.json().catch(() => ({}))) as {
        job_id?: string;
        state?: string;
        reason?: string;
        artifact?: unknown;
      };
      const ok = delegated.state !== "GAP" && delegated.state !== "FAILED";
      return NextResponse.json(
        {
          ok,
          launched: ok,
          target,
          job: delegated,
          message: ok
            ? target.label + " delegated to PDflow local agent"
            : delegated.reason || target.label + " could not be opened",
        },
        { status: ok ? 200 : 503 },
      );
    }
    return NextResponse.json(
      {
        ok: false,
        launched: false,
        target,
        state: "GAP",
        message: "PDflow local agent is unavailable; native launch refused",
      },
      { status: 503 },
    );
  }
  return NextResponse.json(
    { ok: false, launched: false, target, state: "GAP", message: "target is not launchable" },
    { status: 503 },
  );
}

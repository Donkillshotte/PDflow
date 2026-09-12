import { NextResponse } from "next/server";
import {
  layoutPreviewMeta,
  PHASE_LAYOUT,
  resolveLayoutImageAbs,
  type LayoutPhaseId,
} from "@/lib/layoutPreview";
import { agentResponse } from "@/lib/agentClient";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";
import { normalizeResultsVariant } from "@/lib/pathGuard";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const PHASES = new Set(Object.keys(PHASE_LAYOUT));

export async function GET(req: Request) {
  const denied = authorizeStudioMutation(req, "layout preview process");
  if (denied) {
    return denied;
  }
  const url = new URL(req.url);
  const phase = (url.searchParams.get("phase") || "place") as LayoutPhaseId;
  let variant = url.searchParams.get("variant") || "flowlab";
  const runId = url.searchParams.get("run_id");

  if (!PHASES.has(phase)) {
    return NextResponse.json({ error: "invalid phase" }, { status: 400 });
  }

  try {
    variant = normalizeResultsVariant(variant);
    const meta = layoutPreviewMeta(phase, variant, runId);
    const imageUrl = meta.image
      ? `/api/layout-preview/image?phase=${encodeURIComponent(phase)}&variant=${encodeURIComponent(variant)}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`
      : null;

    return NextResponse.json({ ...meta, imageUrl });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: message },
      { status: message.startsWith("REFUSED:") ? 400 : 500 },
    );
  }
}

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "layout preview mutation");
  if (denied) {
    return denied;
  }
  const tooLarge = rejectOversizedBody(req, 32 * 1024);
  if (tooLarge) {
    return tooLarge;
  }
  const requestBody = (await req.json().catch(() => ({}))) as {
    phase?: string;
    variant?: string;
    run_id?: string;
  };
  const phase = (requestBody.phase || "place") as LayoutPhaseId;
  let variant = requestBody.variant || "flowlab";
  const runId = requestBody.run_id;
  if (!PHASES.has(phase)) {
    return NextResponse.json({ error: "invalid phase" }, { status: 400 });
  }
  let resolved: ReturnType<typeof resolveLayoutImageAbs> = null;
  try {
    variant = normalizeResultsVariant(variant);
    resolved = resolveLayoutImageAbs(phase, variant, runId);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 400 });
  }
  if (resolved) {
    return NextResponse.json({
      ok: true,
      source: resolved.source,
      imageUrl: `/api/layout-preview/image?phase=${encodeURIComponent(phase)}&variant=${encodeURIComponent(variant)}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}&t=${Date.now()}`,
    });
  }

  // A live ODB without a current preview is rendered by the authenticated
  // local agent. Next must remain a facade: spawning OpenROAD from a request
  // would bypass the cgroup queue, leak descendants on cancellation, and
  // allow repeated refreshes to create competing native processes.
  const meta = layoutPreviewMeta(phase, variant, runId);
  if (!meta.odbExists) {
    return NextResponse.json(
      { ok: false, message: "Cannot generate preview — run the ORFS phase" },
      { status: 404 },
    );
  }

  const remote = await agentResponse("/v1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: "layout_preview",
      operation: "action",
      variant,
      preview_phase: phase,
      run_id: runId || undefined,
    }),
  });
  if (!remote) {
    return NextResponse.json(
      {
        ok: false,
        state: "GAP",
        message: "Live preview requires the authenticated PDflow local agent",
      },
      { status: 503 },
    );
  }
  const agentJob = (await remote.json().catch(() => ({}))) as {
    job_id?: string;
    state?: string;
    reason?: string | null;
    report?: unknown;
  };
  if (agentJob.state === "GAP") {
    return NextResponse.json(
      { ok: false, state: "GAP", message: agentJob.reason || "Live preview dependency GAP", job: agentJob },
      { status: 412 },
    );
  }
  if (!agentJob.job_id) {
    return NextResponse.json(
      { ok: false, state: "FAIL", message: "Local agent did not return a preview job id" },
      { status: 502 },
    );
  }
  return NextResponse.json(
    {
      ok: true,
      pending: true,
      source: "odb",
      job_id: agentJob.job_id,
      state: agentJob.state || "QUEUED",
      job: agentJob,
      imageUrl: `/api/layout-preview/image?phase=${encodeURIComponent(phase)}&variant=${encodeURIComponent(variant)}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`,
    },
    { status: 202 },
  );
}

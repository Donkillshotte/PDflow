import { NextResponse } from "next/server";
import { isStageInspect } from "@/lib/inspect";
import {
  AgentUnavailableError,
  agentCommandText,
  submitAgentAction,
  waitForAgentJob,
} from "@/lib/agentRun";
import { preferredResultsVariant } from "@/lib/open";
import { normalizeResultsVariant } from "@/lib/pathGuard";
import { authorizeStudioMutation } from "@/lib/runAuth";

export const dynamic = "force-dynamic";
export const maxDuration = 900;

const STAGES = new Set([
  "synth",
  "floorplan",
  "pdn",
  "place",
  "cts",
  "route",
  "finish",
]);

export async function GET(req: Request) {
  const denied = authorizeStudioMutation(req, "inspect process");
  if (denied) {
    return denied;
  }
  const url = new URL(req.url);
  const stage = url.searchParams.get("stage") || "synth";
  const variant = url.searchParams.get("variant") || preferredResultsVariant();
  const runId = url.searchParams.get("run_id");
  if (!STAGES.has(stage)) {
    return NextResponse.json({ error: "invalid stage" }, { status: 400 });
  }
  try {
    const normalizedVariant = normalizeResultsVariant(variant);
    const submit = await submitAgentAction({
      action: "inspect_stage",
      variant: normalizedVariant,
      mode: "view",
      runId: runId || undefined,
      parameters: { stage },
    });
    if (!submit.response) {
      return NextResponse.json(
        { ok: false, status: "GAP", error: "PDflow local agent is not running" },
        { status: 503 },
      );
    }
    if (!submit.response.ok) {
      return NextResponse.json(
        submit.body && typeof submit.body === "object"
          ? submit.body
          : { ok: false, status: "GAP", error: "agent rejected inspection" },
        { status: submit.response.status },
      );
    }
    if (!submit.job) {
      return NextResponse.json(
        { ok: false, status: "GAP", error: "invalid inspection job from agent" },
        { status: 502 },
      );
    }
    if (submit.job.state === "GAP") {
      return NextResponse.json(submit.job, { status: 412 });
    }
    const job = await waitForAgentJob(submit.job);
    const details = job.report?.details;
    if (!isStageInspect(details)) {
      return NextResponse.json(
        {
          ok: false,
          status: job.report?.status || job.state,
          error: job.reason || "agent returned no validated inspection payload",
          command: agentCommandText(job),
          job,
          report: job.report || null,
        },
        { status: job.state === "COMPLETED" ? 502 : 422 },
      );
    }
    const ok = job.state === "COMPLETED" && job.report?.ok === true;
    return NextResponse.json(
      {
        ...details,
        ok,
        status: job.report?.status || details.status,
        job_id: job.job_id,
        report_id: job.report?.report_id,
        resource: job.resource || null,
      },
      { status: ok ? 200 : 422 },
    );
  } catch (e) {
    if (e instanceof AgentUnavailableError) {
      return NextResponse.json(
        { ok: false, status: "GAP", error: e.message },
        { status: 503 },
      );
    }
    if (e instanceof DOMException && e.name === "AbortError") {
      return NextResponse.json(
        { ok: false, status: "CANCELLED", error: "inspection request was cancelled" },
        { status: 499 },
      );
    }
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: message },
      { status: message.startsWith("REFUSED:") ? 400 : 500 },
    );
  }
}

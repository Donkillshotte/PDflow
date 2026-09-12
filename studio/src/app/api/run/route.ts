import { NextResponse } from "next/server";
import { isAllowedAction } from "@/lib/run";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";
import {
  agentCommandText,
  submitAgentAction,
  waitForAgentJob,
} from "@/lib/agentRun";

export const dynamic = "force-dynamic";
export const maxDuration = 900;

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "run");
  if (denied) {
    return denied;
  }
  const tooLarge = rejectOversizedBody(req, 128 * 1024);
  if (tooLarge) {
    return tooLarge;
  }
  const body = (await req.json()) as { action?: string };
  const action = body.action ?? "";
  if (!isAllowedAction(action)) {
    return NextResponse.json(
      { error: `Action not allowed. Use: check, status, list, synth, floorplan, place, cts, route, finish, test_course` },
      { status: 400 },
    );
  }
  const submit = await submitAgentAction({
    action,
    variant: "learn",
    mode: "view",
  });
  if (!submit.response) {
    return NextResponse.json(
      {
        ok: false,
        status: "GAP",
        error: "PDflow local agent is not running",
      },
      { status: 503 },
    );
  }
  if (!submit.response.ok) {
    return NextResponse.json(
      submit.body && typeof submit.body === "object"
        ? submit.body
        : { ok: false, error: "PDflow local agent rejected the action" },
      { status: submit.response.status },
    );
  }
  if (!submit.job) {
    return NextResponse.json(
      { ok: false, status: "GAP", error: "Invalid job record from local agent" },
      { status: 502 },
    );
  }
  if (submit.job.state === "GAP") {
    return NextResponse.json(submit.job, { status: 412 });
  }

  const job = await waitForAgentJob(submit.job);
  const ok = job.state === "COMPLETED" && job.report?.ok === true;
  return NextResponse.json(
    {
      ok,
      status: job.state,
      code: job.code ?? null,
      stdout: job.log_tail || "",
      stderr: ok ? "" : job.reason || job.report?.reason || "",
      command: agentCommandText(job),
      job,
      report: job.report || null,
      reason: job.reason || job.report?.reason || null,
      termination_cause: job.termination_cause || null,
      resource: job.resource || null,
    },
    { status: ok ? 200 : 500 },
  );
}

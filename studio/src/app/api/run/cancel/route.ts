import { NextResponse } from "next/server";
import { cancelAgentJob } from "@/lib/agentRun";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "run cancellation");
  if (denied) {
    return denied;
  }
  const tooLarge = rejectOversizedBody(req, 16 * 1024);
  if (tooLarge) {
    return tooLarge;
  }
  const body = (await req.json()) as { jobId?: string };
  if (!body.jobId) {
    return NextResponse.json({ error: "jobId richiesto" }, { status: 400 });
  }
  const job = await cancelAgentJob(body.jobId);
  if (!job) {
    return NextResponse.json(
      {
        ok: false,
        jobId: body.jobId,
        error: "PDflow local agent could not find or cancel this job",
      },
      { status: 404 },
    );
  }
  return NextResponse.json({ ok: true, jobId: body.jobId, job });
}

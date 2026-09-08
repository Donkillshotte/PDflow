import { NextResponse } from "next/server";
import { cancelJob } from "@/lib/run";
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
  const ok = cancelJob(body.jobId);
  return NextResponse.json({ ok, jobId: body.jobId });
}

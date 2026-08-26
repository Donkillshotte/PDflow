import { NextResponse } from "next/server";
import { cancelJob } from "@/lib/run";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = (await req.json()) as { jobId?: string };
  if (!body.jobId) {
    return NextResponse.json({ error: "jobId richiesto" }, { status: 400 });
  }
  const ok = cancelJob(body.jobId);
  return NextResponse.json({ ok, jobId: body.jobId });
}

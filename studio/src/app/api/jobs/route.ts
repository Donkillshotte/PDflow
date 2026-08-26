import { NextResponse } from "next/server";
import {
  forceReleaseLock,
  getJob,
  getPipelineStatus,
  listJobs,
  readLock,
} from "@/lib/jobs";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const id = url.searchParams.get("id");
  if (id) {
    const job = getJob(id);
    if (!job) {
      return NextResponse.json({ error: "job non trovato" }, { status: 404 });
    }
    return NextResponse.json(job);
  }
  return NextResponse.json({
    jobs: listJobs(Number(url.searchParams.get("limit") || 20)),
    lock: readLock(),
    pipeline: getPipelineStatus(),
  });
}

export async function DELETE(req: Request) {
  const url = new URL(req.url);
  if (url.searchParams.get("force") === "1") {
    forceReleaseLock();
    return NextResponse.json({ ok: true, lock: null });
  }
  return NextResponse.json({ error: "usa ?force=1" }, { status: 400 });
}

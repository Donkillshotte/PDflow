import { NextResponse } from "next/server";
import { agentFetch, agentResponse } from "@/lib/agentClient";
import {
  forceReleaseLock,
  getJob,
  getPipelineStatus,
  listJobs,
  readLock,
  pidAlive,
} from "@/lib/jobs";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const id = url.searchParams.get("id");
  if (id) {
    const remote = await agentFetch(
      "/v1/jobs?id=" + encodeURIComponent(id),
    );
    if (remote) return NextResponse.json(remote);
    const job = getJob(id);
    if (!job) {
      return NextResponse.json({ error: "job not found" }, { status: 404 });
    }
    return NextResponse.json(job);
  }
  return NextResponse.json({
    jobs: listJobs(Number(url.searchParams.get("limit") || 20)),
    agent: await agentFetch("/v1/jobs"),
    lock: readLock(),
    pipeline: getPipelineStatus(),
  });
}

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "submit PDflow agent job");
  if (denied) return denied;
  const tooLarge = rejectOversizedBody(req, 64 * 1024);
  if (tooLarge) return tooLarge;
  const payload = await req.json();
  const remote = await agentResponse("/v1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!remote) {
    return NextResponse.json(
      { ok: false, state: "GAP", error: "PDflow local agent is not running" },
      { status: 503 },
    );
  }
  const body = await remote.json().catch(() => ({
    ok: false,
    state: "GAP",
    error: "invalid response from PDflow local agent",
  }));
  return NextResponse.json(body, { status: remote.status });
}

export async function DELETE(req: Request) {
  const denied = authorizeStudioMutation(req, "job lock mutation");
  if (denied) {
    return denied;
  }
  const tooLarge = rejectOversizedBody(req, 16 * 1024);
  if (tooLarge) {
    return tooLarge;
  }
  const url = new URL(req.url);
  if (url.searchParams.get("force") === "1") {
    const lock = readLock();
    const runningPid = lock?.childPid ?? lock?.pid;
    if (runningPid && pidAlive(runningPid)) {
      return NextResponse.json(
        { error: "job still running; cancel it first", lock },
        { status: 409 },
      );
    }
    forceReleaseLock();
    return NextResponse.json({ ok: true, lock: null });
  }
  return NextResponse.json({ error: "usa ?force=1" }, { status: 400 });
}

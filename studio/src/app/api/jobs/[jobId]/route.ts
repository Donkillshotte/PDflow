import { NextResponse } from "next/server";
import { agentFetch } from "@/lib/agentClient";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ jobId: string }> };

export async function GET(_req: Request, context: RouteContext) {
  const { jobId } = await context.params;
  const remote = await agentFetch(
    "/v1/jobs?id=" + encodeURIComponent(jobId),
  );
  if (!remote) {
    return NextResponse.json(
      { state: "GAP", error: "PDflow local agent is not running" },
      { status: 503 },
    );
  }
  return NextResponse.json(remote);
}

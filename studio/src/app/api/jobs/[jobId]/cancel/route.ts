import { NextResponse } from "next/server";
import { agentResponse } from "@/lib/agentClient";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ jobId: string }> };

export async function POST(req: Request, context: RouteContext) {
  const denied = authorizeStudioMutation(req, "cancel PDflow job");
  if (denied) return denied;
  const tooLarge = rejectOversizedBody(req, 8 * 1024);
  if (tooLarge) return tooLarge;
  const { jobId } = await context.params;
  const remote = await agentResponse(
    "/v1/jobs/" + encodeURIComponent(jobId) + "/cancel",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    },
  );
  if (!remote) {
    return NextResponse.json(
      { state: "GAP", error: "PDflow local agent is not running" },
      { status: 503 },
    );
  }
  const body = await remote.json().catch(() => ({
    state: "GAP",
    error: "invalid response from PDflow local agent",
  }));
  return NextResponse.json(body, { status: remote.status });
}

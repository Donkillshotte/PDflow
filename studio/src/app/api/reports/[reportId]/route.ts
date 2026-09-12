import { NextResponse } from "next/server";
import { agentResponse } from "@/lib/agentClient";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ reportId: string }> };

export async function GET(_req: Request, context: RouteContext) {
  const { reportId } = await context.params;
  const remote = await agentResponse(
    "/v1/reports/" + encodeURIComponent(reportId),
  );
  if (!remote) {
    return NextResponse.json(
      {
        status: "GAP",
        ok: false,
        stale: true,
        reason: "report unavailable because the local agent is offline",
      },
      { status: 503 },
    );
  }
  const body = await remote.json().catch(() => ({
    status: "GAP",
    ok: false,
    stale: true,
    reason: "invalid response from PDflow local agent",
  }));
  return NextResponse.json(body, { status: remote.status });
}

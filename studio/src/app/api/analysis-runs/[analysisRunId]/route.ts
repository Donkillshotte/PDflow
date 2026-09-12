import { NextResponse } from "next/server";
import { agentFetch } from "@/lib/agentClient";

export const dynamic = "force-dynamic";

const SAFE_ID = /^[A-Za-z0-9_.-]{8,100}$/;

export async function GET(
  _req: Request,
  context: { params: Promise<{ analysisRunId: string }> },
) {
  const { analysisRunId } = await context.params;
  if (!SAFE_ID.test(analysisRunId)) {
    return NextResponse.json({ error: "invalid analysis_run_id" }, { status: 400 });
  }
  const remote = await agentFetch(
    "/v1/analysis-runs/" + encodeURIComponent(analysisRunId),
  );
  if (!remote) {
    return NextResponse.json(
      { error: "analysis run unavailable because the local agent is offline" },
      { status: 503 },
    );
  }
  return NextResponse.json(remote);
}

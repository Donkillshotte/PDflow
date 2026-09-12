import { NextResponse } from "next/server";
import { agentFetch, agentResponse } from "@/lib/agentClient";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const limit = new URL(req.url).searchParams.get("limit") || "40";
  const remote = await agentFetch(
    "/v1/analysis-runs?limit=" + encodeURIComponent(limit),
  );
  return NextResponse.json(remote || { analysis_runs: [], source: "agent-offline" });
}

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "create analysis run");
  if (denied) return denied;
  const tooLarge = rejectOversizedBody(req, 64 * 1024);
  if (tooLarge) return tooLarge;
  const payload = await req.json();
  const remote = await agentResponse("/v1/analysis-runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!remote) {
    return NextResponse.json(
      { ok: false, status: "GAP", error: "PDflow local agent is not running" },
      { status: 503 },
    );
  }
  const body = await remote.json().catch(() => ({
    ok: false,
    status: "GAP",
    error: "invalid response from PDflow local agent",
  }));
  return NextResponse.json(body, { status: remote.status });
}

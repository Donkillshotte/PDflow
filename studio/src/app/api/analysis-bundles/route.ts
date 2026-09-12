import { NextResponse } from "next/server";
import { agentResponse } from "@/lib/agentClient";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "execute analysis bundle");
  if (denied) return denied;
  const tooLarge = rejectOversizedBody(req, 64 * 1024);
  if (tooLarge) return tooLarge;
  const payload = await req.json();
  const remote = await agentResponse("/v1/analysis-bundles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!remote) {
    return NextResponse.json(
      { status: "GAP", ok: false, reason: "PDflow local agent is not running" },
      { status: 503 },
    );
  }
  const body = await remote.json().catch(() => ({
    status: "GAP",
    ok: false,
    reason: "invalid response from PDflow local agent",
  }));
  return NextResponse.json(body, { status: remote.status });
}

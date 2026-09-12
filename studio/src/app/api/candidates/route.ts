import { NextResponse } from "next/server";
import { agentResponse } from "@/lib/agentClient";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "create PDflow candidate");
  if (denied) return denied;
  const tooLarge = rejectOversizedBody(req, 32 * 1024);
  if (tooLarge) return tooLarge;
  const payload = await req.json();
  const remote = await agentResponse("/v1/candidates", {
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
    status: "GAP",
    error: "invalid response from PDflow local agent",
  }));
  return NextResponse.json(body, { status: remote.status });
}

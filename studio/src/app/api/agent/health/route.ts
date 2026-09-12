import { NextResponse } from "next/server";
import { agentFetch } from "@/lib/agentClient";

export const dynamic = "force-dynamic";

export async function GET() {
  const remote = await agentFetch("/health");
  return NextResponse.json(
    remote || {
      ok: false,
      service: "pdflow-local-agent",
      state: "GAP",
      reason: "local agent is not running",
    },
  );
}

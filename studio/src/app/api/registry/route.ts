import { NextResponse } from "next/server";
import { agentFetch } from "@/lib/agentClient";
import { discoverStudioTools } from "@/lib/pdflowRegistry";

export const dynamic = "force-dynamic";

export async function GET() {
  const remote = await agentFetch("/v1/registry");
  return NextResponse.json(remote || discoverStudioTools());
}

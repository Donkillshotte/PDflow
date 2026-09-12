import { NextResponse } from "next/server";
import { agentFetch } from "@/lib/agentClient";
import { fallbackContext } from "@/lib/pdflowContext";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const params = new URL(req.url).searchParams;
  const limit = params.get("limit") || "200";
  const query = new URLSearchParams({ limit });
  for (const key of ["scope", "variant", "authority", "run_id"]) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  const remote = await agentFetch(
    "/v1/artifacts?" + query.toString(),
  );
  if (remote) return NextResponse.json(remote);
  const context = fallbackContext("flow");
  return NextResponse.json({
    schema_version: 1,
    artifacts: [...context.finish, ...context.candidates],
    count: context.finish.length + context.candidates.length,
    source: "studio-fallback",
  });
}

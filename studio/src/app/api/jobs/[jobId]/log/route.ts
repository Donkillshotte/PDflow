import { NextResponse } from "next/server";
import { agentResponse } from "@/lib/agentClient";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ jobId: string }> };

/**
 * Stream the complete agent-owned log as a download. The UI only keeps a
 * bounded tail; this route deliberately forwards the file without parsing it
 * into a JSON response or duplicating it in the Next process.
 */
export async function GET(_req: Request, context: RouteContext) {
  const { jobId } = await context.params;
  const remote = await agentResponse(
    "/v1/jobs/" + encodeURIComponent(jobId) + "/log",
  );
  if (!remote) {
    return NextResponse.json(
      { error: "PDflow local agent is not running" },
      { status: 503 },
    );
  }
  if (!remote.ok || !remote.body) {
    const body = await remote.json().catch(() => ({ error: "log not found" }));
    return NextResponse.json(body, { status: remote.status });
  }
  const headers = new Headers();
  for (const name of [
    "content-type",
    "content-length",
    "content-disposition",
    "cache-control",
    "x-content-type-options",
  ]) {
    const value = remote.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new NextResponse(remote.body, {
    status: remote.status,
    headers,
  });
}

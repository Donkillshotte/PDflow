import { NextResponse } from "next/server";
import { agentFetch, agentResponse } from "@/lib/agentClient";
import { fallbackContext } from "@/lib/pdflowContext";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ artifactId: string }> };

export async function GET(_req: Request, context: RouteContext) {
  const { artifactId } = await context.params;
  const remote = await agentFetch(
    "/v1/artifacts/" + encodeURIComponent(artifactId),
  );
  if (remote) return NextResponse.json(remote);
  const fallbackArtifacts = [
    ...fallbackContext("flow").finish,
    ...fallbackContext("flow").candidates,
  ];
  const fallback = fallbackArtifacts.find(
    (artifact) => artifact.artifact_id === artifactId,
  );
  if (!fallback) {
    return NextResponse.json({ error: "artifact not found" }, { status: 404 });
  }
  return NextResponse.json({
    schema_version: 1,
    artifact: fallback,
    resolved: true,
    read_only: !fallback.mutable,
    source: "studio-fallback",
  });
}

export async function POST(req: Request, context: RouteContext) {
  const denied = authorizeStudioMutation(req, "open PDflow artifact");
  if (denied) return denied;
  const tooLarge = rejectOversizedBody(req, 16 * 1024);
  if (tooLarge) return tooLarge;
  const { artifactId } = await context.params;
  const body = (await req.json().catch(() => ({}))) as {
    mode?: "view" | "edit";
    run_id?: string;
  };
  if (body.mode === "edit" && !body.run_id) {
    return NextResponse.json(
      {
        ok: false,
        state: "GAP",
        error: "editable artifact launch requires a candidate run_id",
      },
      { status: 400 },
    );
  }
  const detail = await agentFetch<{
    artifact?: { kind?: string; mutable?: boolean };
  }>("/v1/artifacts/" + encodeURIComponent(artifactId));
  const kind = detail?.artifact?.kind;
  const tool_id =
    kind === "gds" || kind === "oas" || kind === "lyrdb"
      ? "klayout"
      : "openroad";
  const remote = await agentResponse("/v1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tool_id,
      operation: "gui",
      artifact_id: artifactId,
      mode: body.mode || "view",
      run_id: body.run_id,
    }),
  });
  if (!remote) {
    return NextResponse.json(
      { ok: false, state: "GAP", error: "PDflow local agent is not running" },
      { status: 503 },
    );
  }
  const responseBody = await remote.json().catch(() => ({
    ok: false,
    state: "GAP",
    error: "invalid response from PDflow local agent",
  }));
  const delegated = responseBody as {
    state?: string;
    reason?: string;
    job_id?: string;
  };
  const launched =
    Boolean(delegated.job_id) &&
    delegated.state !== "GAP" &&
    delegated.state !== "FAILED";
  return NextResponse.json(
    {
      ...responseBody,
      ok: launched,
      launched,
      message: launched
        ? "Native tool delegated to the PDflow local agent"
        : delegated.reason || "Native tool could not be started",
    },
    { status: launched ? 200 : remote.status >= 400 ? remote.status : 503 },
  );
}

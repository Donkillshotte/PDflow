import { NextResponse } from "next/server";
import { startViewer, stopViewer, viewerStatus } from "@/lib/webviewer";
import { preferredResultsVariant } from "@/lib/open";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(await viewerStatus());
}

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "web viewer mutation");
  if (denied) {
    return denied;
  }
  const tooLarge = rejectOversizedBody(req, 32 * 1024);
  if (tooLarge) {
    return tooLarge;
  }
  const body = (await req.json().catch(() => ({}))) as {
    action?: string;
    stage?: string;
    variant?: string;
    artifact?: string;
    run_id?: string;
  };
  const action = body.action || "start";
  if (action === "stop") {
    return NextResponse.json(await stopViewer());
  }
  if (action === "start") {
    const stage = body.stage || "cts";
    const variant = body.variant || preferredResultsVariant();
    try {
      const result = await startViewer(stage, variant, {
        artifact: body.artifact,
        runId: body.run_id,
      });
      return NextResponse.json(result, { status: result.ok ? 200 : 422 });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      return NextResponse.json({ ok: false, message }, { status: 400 });
    }
  }
  return NextResponse.json({ error: "invalid action" }, { status: 400 });
}

export async function DELETE(req: Request) {
  const denied = authorizeStudioMutation(req, "web viewer mutation");
  if (denied) {
    return denied;
  }
  const tooLarge = rejectOversizedBody(req, 16 * 1024);
  if (tooLarge) {
    return tooLarge;
  }
  return NextResponse.json(await stopViewer());
}

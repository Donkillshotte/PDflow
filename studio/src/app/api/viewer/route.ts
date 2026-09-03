import { NextResponse } from "next/server";
import { startViewer, stopViewer, viewerStatus } from "@/lib/webviewer";
import { preferredResultsVariant } from "@/lib/open";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(viewerStatus());
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as {
    action?: string;
    stage?: string;
    variant?: string;
    artifact?: string;
  };
  const action = body.action || "start";
  if (action === "stop") {
    return NextResponse.json(stopViewer());
  }
  if (action === "start") {
    const stage = body.stage || "cts";
    const variant = body.variant || preferredResultsVariant();
    const result = startViewer(stage, variant, {
      artifact: body.artifact,
    });
    return NextResponse.json(result, { status: result.ok ? 200 : 422 });
  }
  return NextResponse.json({ error: "invalid action" }, { status: 400 });
}

export async function DELETE() {
  return NextResponse.json(stopViewer());
}

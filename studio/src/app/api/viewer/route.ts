import { NextResponse } from "next/server";
import { startViewer, stopViewer, viewerStatus } from "@/lib/webviewer";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(viewerStatus());
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as {
    action?: string;
    stage?: string;
    variant?: string;
  };
  const action = body.action || "start";
  if (action === "stop") {
    return NextResponse.json(stopViewer());
  }
  if (action === "start") {
    const stage = body.stage || "cts";
    const variant = body.variant || "learn";
    const result = startViewer(stage, variant);
    return NextResponse.json(result, { status: result.ok ? 200 : 422 });
  }
  return NextResponse.json({ error: "action non valida" }, { status: 400 });
}

export async function DELETE() {
  return NextResponse.json(stopViewer());
}

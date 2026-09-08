import { NextResponse } from "next/server";
import { collectStageResults } from "@/lib/results";
import { preferredResultsVariant } from "@/lib/open";
import { normalizeResultsVariant } from "@/lib/pathGuard";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const stage = url.searchParams.get("stage") ?? "synth";
  const variant = url.searchParams.get("variant") ?? preferredResultsVariant();
  try {
    return NextResponse.json(
      collectStageResults(stage, normalizeResultsVariant(variant)),
    );
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: message },
      { status: message.startsWith("REFUSED:") ? 400 : 500 },
    );
  }
}

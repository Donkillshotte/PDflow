import { NextResponse } from "next/server";
import { inspectStage } from "@/lib/inspect";
import { preferredResultsVariant } from "@/lib/open";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const STAGES = new Set([
  "synth",
  "floorplan",
  "pdn",
  "place",
  "cts",
  "route",
  "finish",
]);

export async function GET(req: Request) {
  const url = new URL(req.url);
  const stage = url.searchParams.get("stage") || "synth";
  const variant = url.searchParams.get("variant") || preferredResultsVariant();
  if (!STAGES.has(stage)) {
    return NextResponse.json({ error: "invalid stage" }, { status: 400 });
  }
  try {
    const data = inspectStage(stage, variant);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 },
    );
  }
}

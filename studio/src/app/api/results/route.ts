import { NextResponse } from "next/server";
import { collectStageResults } from "@/lib/results";
import { preferredResultsVariant } from "@/lib/open";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const stage = url.searchParams.get("stage") ?? "synth";
  const variant = url.searchParams.get("variant") ?? preferredResultsVariant();
  return NextResponse.json(collectStageResults(stage, variant));
}

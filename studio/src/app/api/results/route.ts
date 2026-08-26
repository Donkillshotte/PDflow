import { NextResponse } from "next/server";
import { collectStageResults } from "@/lib/results";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const stage = url.searchParams.get("stage") ?? "synth";
  const variant = url.searchParams.get("variant") ?? "learn";
  return NextResponse.json(collectStageResults(stage, variant));
}

import { NextResponse } from "next/server";
import { collectStageResults } from "@/lib/results";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const stage = new URL(req.url).searchParams.get("stage") ?? "synth";
  return NextResponse.json(collectStageResults(stage));
}

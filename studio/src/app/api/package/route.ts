import { NextResponse } from "next/server";
import { getPackageEvidence } from "@/lib/pdflowAnalysis";
import { normalizeResultsVariant } from "@/lib/pathGuard";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const raw = new URL(req.url).searchParams.get("variant");
  try {
    const variant = raw ? normalizeResultsVariant(raw) : undefined;
    return NextResponse.json(await getPackageEvidence(variant));
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 400 });
  }
}

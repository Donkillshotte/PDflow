import { NextResponse } from "next/server";
import { getStudioContext } from "@/lib/pdflowContext";
import type { Surface } from "@/lib/pdflowContracts";

export const dynamic = "force-dynamic";

const SURFACES = new Set<Surface>([
  "product",
  "flow",
  "package",
  "lab",
  "tools",
]);

export async function GET(req: Request) {
  const surface = new URL(req.url).searchParams.get("surface") as Surface | null;
  return NextResponse.json(
    await getStudioContext(surface && SURFACES.has(surface) ? surface : "flow"),
  );
}

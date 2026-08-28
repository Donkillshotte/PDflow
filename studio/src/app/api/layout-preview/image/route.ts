import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import {
  PHASE_LAYOUT,
  resolveLayoutImageAbs,
  type LayoutPhaseId,
} from "@/lib/layoutPreview";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const PHASES = new Set(Object.keys(PHASE_LAYOUT));

const MIME: Record<string, string> = {
  ".png": "image/png",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".jpeg": "image/jpeg",
};

export async function GET(req: Request) {
  const url = new URL(req.url);
  const phase = (url.searchParams.get("phase") || "place") as LayoutPhaseId;
  const variant = url.searchParams.get("variant") || "flowlab";

  if (!PHASES.has(phase)) {
    return NextResponse.json({ error: "phase non valido" }, { status: 400 });
  }

  const resolved = resolveLayoutImageAbs(phase, variant);
  if (!resolved) {
    return NextResponse.json(
      { error: "Preview assente — esegui la fase o genera da ODB" },
      { status: 404 },
    );
  }

  const buf = fs.readFileSync(resolved.abs);
  const ext = path.extname(resolved.abs).toLowerCase();
  return new NextResponse(buf, {
    headers: {
      "Content-Type": MIME[ext] || "application/octet-stream",
      "Cache-Control": "private, max-age=120",
      "X-Layout-Source": resolved.source,
    },
  });
}

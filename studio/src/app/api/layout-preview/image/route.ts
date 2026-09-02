import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import {
  PHASE_LAYOUT,
  resolveLayoutImageAbs,
  resolveNamedGuiShot,
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
  ".jpg": "image/jpeg",
};

function sendFile(abs: string, extra: Record<string, string> = {}) {
  const buf = fs.readFileSync(abs);
  const ext = path.extname(abs).toLowerCase();
  return new NextResponse(buf, {
    headers: {
      "Content-Type": MIME[ext] || "application/octet-stream",
      "Cache-Control": "private, max-age=120",
      ...extra,
    },
  });
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const shot = url.searchParams.get("shot");
  if (shot) {
    const abs = resolveNamedGuiShot(shot);
    if (!abs) {
      const invalid = !/^[A-Za-z0-9._-]+\.(png|webp|jpe?g)$/.test(shot);
      return NextResponse.json(
        { error: invalid ? "invalid shot" : "shot missing" },
        { status: invalid ? 400 : 404 },
      );
    }
    return sendFile(abs, { "X-Layout-Source": "gui_shot" });
  }

  const phase = (url.searchParams.get("phase") || "place") as LayoutPhaseId;
  const variant = url.searchParams.get("variant") || "flowlab";

  if (!PHASES.has(phase)) {
    return NextResponse.json({ error: "invalid phase" }, { status: 400 });
  }

  const resolved = resolveLayoutImageAbs(phase, variant);
  if (!resolved) {
    return NextResponse.json(
      { error: "Preview missing — run the phase or generate from ODB" },
      { status: 404 },
    );
  }

  return sendFile(resolved.abs, { "X-Layout-Source": resolved.source });
}

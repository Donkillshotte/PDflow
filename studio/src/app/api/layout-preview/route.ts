import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import {
  layoutPreviewMeta,
  PHASE_LAYOUT,
  resolveLayoutImageAbs,
  type LayoutPhaseId,
} from "@/lib/layoutPreview";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const PHASES = new Set(Object.keys(PHASE_LAYOUT));

export async function GET(req: Request) {
  const url = new URL(req.url);
  const phase = (url.searchParams.get("phase") || "place") as LayoutPhaseId;
  const variant = url.searchParams.get("variant") || "flowlab";

  if (!PHASES.has(phase)) {
    return NextResponse.json({ error: "invalid phase" }, { status: 400 });
  }

  const meta = layoutPreviewMeta(phase, variant);
  const imageUrl = meta.image
    ? `/api/layout-preview/image?phase=${encodeURIComponent(phase)}&variant=${encodeURIComponent(variant)}`
    : null;

  return NextResponse.json({ ...meta, imageUrl });
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as {
    phase?: string;
    variant?: string;
  };
  const phase = (body.phase || "place") as LayoutPhaseId;
  const variant = body.variant || "flowlab";
  if (!PHASES.has(phase)) {
    return NextResponse.json({ error: "invalid phase" }, { status: 400 });
  }
  const resolved = resolveLayoutImageAbs(phase, variant);
  if (!resolved) {
    return NextResponse.json(
      { ok: false, message: "Cannot generate preview — run the ORFS phase" },
      { status: 404 },
    );
  }
  return NextResponse.json({
    ok: true,
    source: resolved.source,
    imageUrl: `/api/layout-preview/image?phase=${encodeURIComponent(phase)}&variant=${encodeURIComponent(variant)}&t=${Date.now()}`,
  });
}

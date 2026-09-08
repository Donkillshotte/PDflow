import { NextResponse } from "next/server";
import {
  layoutPreviewMeta,
  PHASE_LAYOUT,
  resolveLayoutImageAbs,
  type LayoutPhaseId,
} from "@/lib/layoutPreview";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";
import { normalizeResultsVariant } from "@/lib/pathGuard";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const PHASES = new Set(Object.keys(PHASE_LAYOUT));

export async function GET(req: Request) {
  const denied = authorizeStudioMutation(req, "layout preview process");
  if (denied) {
    return denied;
  }
  const url = new URL(req.url);
  const phase = (url.searchParams.get("phase") || "place") as LayoutPhaseId;
  let variant = url.searchParams.get("variant") || "flowlab";

  if (!PHASES.has(phase)) {
    return NextResponse.json({ error: "invalid phase" }, { status: 400 });
  }

  try {
    variant = normalizeResultsVariant(variant);
    const meta = layoutPreviewMeta(phase, variant);
    const imageUrl = meta.image
      ? `/api/layout-preview/image?phase=${encodeURIComponent(phase)}&variant=${encodeURIComponent(variant)}`
      : null;

    return NextResponse.json({ ...meta, imageUrl });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: message },
      { status: message.startsWith("REFUSED:") ? 400 : 500 },
    );
  }
}

export async function POST(req: Request) {
  const denied = authorizeStudioMutation(req, "layout preview mutation");
  if (denied) {
    return denied;
  }
  const tooLarge = rejectOversizedBody(req, 32 * 1024);
  if (tooLarge) {
    return tooLarge;
  }
  const body = (await req.json().catch(() => ({}))) as {
    phase?: string;
    variant?: string;
  };
  const phase = (body.phase || "place") as LayoutPhaseId;
  let variant = body.variant || "flowlab";
  if (!PHASES.has(phase)) {
    return NextResponse.json({ error: "invalid phase" }, { status: 400 });
  }
  let resolved: ReturnType<typeof resolveLayoutImageAbs> = null;
  try {
    variant = normalizeResultsVariant(variant);
    resolved = resolveLayoutImageAbs(phase, variant);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 400 });
  }
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

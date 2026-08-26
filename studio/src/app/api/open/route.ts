import { NextResponse } from "next/server";
import {
  launchExternal,
  listOpenTargets,
  resolveArtifactOpen,
  resolveOpenTarget,
} from "@/lib/open";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(listOpenTargets());
}

export async function POST(req: Request) {
  const body = (await req.json()) as {
    id?: string;
    artifact?: string;
    dryRun?: boolean;
  };

  let target = body.id ? resolveOpenTarget(body.id) : null;
  if (!target && body.artifact) {
    target = resolveArtifactOpen(body.artifact);
  }
  if (!target) {
    return NextResponse.json(
      { error: "target non trovato", ok: false },
      { status: 404 },
    );
  }

  // In-app targets: just return href
  if (
    target.kind === "dashboard" ||
    target.kind === "gallery" ||
    target.kind === "doc" ||
    target.kind === "lesson"
  ) {
    return NextResponse.json({
      ok: true,
      launched: false,
      navigate: target.href,
      target,
      message: `Apri ${target.label}`,
    });
  }

  if (body.dryRun) {
    return NextResponse.json({
      ok: target.exists,
      launched: false,
      target,
      command: target.command,
      message: target.exists
        ? "dry-run ok"
        : `Artefatto mancante: ${target.artifact}`,
    });
  }

  const result = launchExternal(target);
  return NextResponse.json(
    { ...result, target },
    { status: result.ok ? 200 : result.display ? 500 : 503 },
  );
}

import { NextResponse } from "next/server";
import {
  launchExternal,
  listOpenTargets,
  resolveArtifactOpen,
  resolveOpenTarget,
} from "@/lib/open";
import { startViewer } from "@/lib/webviewer";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(listOpenTargets());
}

export async function POST(req: Request) {
  const body = (await req.json()) as {
    id?: string;
    artifact?: string;
    dryRun?: boolean;
    variant?: string;
  };

  let target = body.id ? resolveOpenTarget(body.id) : null;
  if (!target && body.artifact) {
    target = resolveArtifactOpen(body.artifact, body.variant ?? "learn");
  }
  if (!target) {
    return NextResponse.json(
      { error: "target non trovato", ok: false },
      { status: 404 },
    );
  }

  // In-app navigation targets
  if (
    target.kind === "dashboard" ||
    target.kind === "gallery" ||
    target.kind === "doc" ||
    target.kind === "lesson" ||
    target.kind === "run"
  ) {
    return NextResponse.json({
      ok: true,
      launched: false,
      navigate: target.href,
      target,
      message: `Apri ${target.label}`,
    });
  }

  if (target.kind === "webviewer") {
    if (body.dryRun) {
      return NextResponse.json({
        ok: target.exists,
        launched: false,
        target,
        message: target.exists
          ? "dry-run webviewer ok"
          : `Artefatto mancante: ${target.artifact}`,
      });
    }
    if (!target.exists || !target.stage) {
      return NextResponse.json(
        {
          ok: false,
          launched: false,
          message: `ODB mancante per web viewer (${target.stage ?? "?"})`,
          target,
        },
        { status: 412 },
      );
    }
    const started = startViewer(target.stage);
    return NextResponse.json(
      {
        ...started,
        launched: Boolean(started.ok && started.url),
        navigate: target.href,
        url: started.url,
        target,
      },
      { status: started.ok ? 200 : 412 },
    );
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

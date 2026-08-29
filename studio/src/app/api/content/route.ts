import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { resolveLearnContent, LEARN_ROOT } from "@/lib/course";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const rel = url.searchParams.get("path") ?? "";
  const abs = resolveLearnContent(rel);
  if (!abs) {
    return NextResponse.json({ error: "Percorso non consentito" }, { status: 404 });
  }
  const ext = path.extname(abs).toLowerCase();
  if (ext === ".svg") {
    const buf = fs.readFileSync(abs);
    return new NextResponse(buf, {
      headers: {
        "Content-Type": "image/svg+xml; charset=utf-8",
        "Cache-Control": "no-store, must-revalidate",
      },
    });
  }
  if (ext === ".png" || ext === ".jpg" || ext === ".jpeg" || ext === ".webp") {
    const buf = fs.readFileSync(abs);
    const type =
      ext === ".png"
        ? "image/png"
        : ext === ".webp"
          ? "image/webp"
          : "image/jpeg";
    return new NextResponse(buf, {
      headers: { "Content-Type": type, "Cache-Control": "public, max-age=3600" },
    });
  }
  const text = fs.readFileSync(abs, "utf8");
  return NextResponse.json(
    {
      path: path.relative(LEARN_ROOT, abs),
      content: text,
    },
    {
      headers: {
        "Cache-Control": "no-store, must-revalidate",
      },
    },
  );
}

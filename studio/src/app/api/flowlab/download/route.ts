import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { LEARN_ROOT, resolveLearnContent } from "@/lib/course";

export const dynamic = "force-dynamic";

const FIXED = {
  vcd: path.join(/*turbopackIgnore: true*/ LEARN_ROOT, "sim/gcd/gcd.vcd"),
  simlog: path.join(/*turbopackIgnore: true*/ LEARN_ROOT, "sim/gcd/sim.log"),
} as const;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const kind = url.searchParams.get("kind");

  if (kind === "vcd" || kind === "simlog") {
    const file = FIXED[kind];
    if (!fs.existsSync(file)) {
      return NextResponse.json({ error: "file not found — run rtl_sim" }, { status: 404 });
    }
    const buf = fs.readFileSync(file);
    const name = kind === "vcd" ? "gcd.vcd" : "sim.log";
    return new NextResponse(buf, {
      headers: {
        "Content-Type": kind === "vcd" ? "application/octet-stream" : "text/plain; charset=utf-8",
        "Content-Disposition": `attachment; filename="${name}"`,
      },
    });
  }

  if (kind === "spice" || kind === "report") {
    const rel = url.searchParams.get("path") ?? "";
    const abs = resolveLearnContent(rel);
    if (!abs) {
      return NextResponse.json({ error: "Path not allowed" }, { status: 404 });
    }
    const buf = fs.readFileSync(abs);
    const name = path.basename(abs);
    const ext = path.extname(abs).toLowerCase();
    const type =
      ext === ".json"
        ? "application/json"
        : ext === ".sp"
          ? "text/plain; charset=utf-8"
          : "application/octet-stream";
    return new NextResponse(buf, {
      headers: {
        "Content-Type": type,
        "Content-Disposition": `attachment; filename="${name}"`,
      },
    });
  }

  return NextResponse.json({ error: "kind=vcd|simlog|spice|report" }, { status: 400 });
}

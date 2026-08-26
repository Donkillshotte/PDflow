import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { LEARN_ROOT } from "@/lib/course";

export const dynamic = "force-dynamic";

const ALLOWED = {
  vcd: path.join(/*turbopackIgnore: true*/ LEARN_ROOT, "sim/gcd/gcd.vcd"),
  simlog: path.join(/*turbopackIgnore: true*/ LEARN_ROOT, "sim/gcd/sim.log"),
} as const;

export async function GET(req: Request) {
  const kind = new URL(req.url).searchParams.get("kind");
  if (kind !== "vcd" && kind !== "simlog") {
    return NextResponse.json({ error: "kind=vcd|simlog" }, { status: 400 });
  }
  const file = ALLOWED[kind];
  if (!fs.existsSync(file)) {
    return NextResponse.json({ error: "file non trovato — esegui rtl_sim" }, { status: 404 });
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

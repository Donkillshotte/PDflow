import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { LEARN_ROOT } from "@/lib/course";

export const dynamic = "force-dynamic";

const ALLOWED = new Set([
  "eco_flowlab.json",
  "eco_learn.json",
  "eco_apply_eco_scratch.json",
  "lvs_signoff_flowlab.json",
  "signoff_all_flowlab.json",
  "signoff_all_eco_scratch.json",
  "drc_deck_coverage.json",
  "power_signoff_flowlab.json",
]);

export async function GET(req: Request) {
  const url = new URL(req.url);
  const name = url.searchParams.get("name") ?? "";
  if (!ALLOWED.has(name)) {
    return NextResponse.json({ error: "unknown report" }, { status: 404 });
  }
  const file = path.join(LEARN_ROOT, "sim/reports", name);
  if (!fs.existsSync(file)) {
    return NextResponse.json({ error: "missing" }, { status: 404 });
  }
  return NextResponse.json(JSON.parse(fs.readFileSync(file, "utf8")));
}

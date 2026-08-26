import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { LEARN_ROOT } from "@/lib/course";

export const dynamic = "force-dynamic";

export async function GET() {
  const dir = path.join(LEARN_ROOT, "reference/gui-shots");
  if (!fs.existsSync(dir)) {
    return NextResponse.json({ shots: [] });
  }
  const shots = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".png"))
    .sort()
    .map((name) => ({
      name,
      href: `/api/content?path=${encodeURIComponent(`reference/gui-shots/${name}`)}`,
      label: name.replace(/\.png$/, "").replace(/_/g, " "),
    }));
  return NextResponse.json({ shots });
}

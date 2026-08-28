import { NextResponse } from "next/server";
import path from "path";
import { LEARN_ROOT } from "@/lib/course";
import { parseVcdWaveform } from "@/lib/vcdWaveform";

export const dynamic = "force-dynamic";

export async function GET() {
  const vcdPath = path.join(LEARN_ROOT, "sim/gcd/gcd.vcd");
  const data = parseVcdWaveform(vcdPath);
  if (!data) {
    return NextResponse.json(
      { exists: false, message: "gcd.vcd assente — esegui rtl_sim" },
      { status: 404 },
    );
  }
  return NextResponse.json(data);
}

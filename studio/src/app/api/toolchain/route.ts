import { NextResponse } from "next/server";
import { probeToolchain } from "@/lib/run";

export const dynamic = "force-dynamic";

export async function GET() {
  const status = await probeToolchain();
  const coreOk = status.tools
    .filter((t) => t.required !== false)
    .every((t) => t.ok);
  const allOk = coreOk && status.orfs && status.tutorial;
  return NextResponse.json({ ...status, ready: allOk });
}

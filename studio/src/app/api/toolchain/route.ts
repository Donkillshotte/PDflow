import { NextResponse } from "next/server";
import { probeToolchain } from "@/lib/run";

export const dynamic = "force-dynamic";

export async function GET() {
  const status = await probeToolchain();
  const allOk =
    status.tools.every((t) => t.ok) && status.orfs && status.tutorial;
  return NextResponse.json({ ...status, ready: allOk });
}

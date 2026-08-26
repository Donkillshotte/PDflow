import { NextResponse } from "next/server";
import { getSuiteStatus } from "@/lib/suite";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const status = await getSuiteStatus();
    return NextResponse.json(status);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 },
    );
  }
}

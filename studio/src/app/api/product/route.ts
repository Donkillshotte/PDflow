import { NextResponse } from "next/server";
import { getProductSnapshot } from "@/lib/product";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(getProductSnapshot());
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 },
    );
  }
}

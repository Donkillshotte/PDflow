import { NextResponse } from "next/server";
import { getProductStory } from "@/lib/story";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(getProductStory());
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 },
    );
  }
}

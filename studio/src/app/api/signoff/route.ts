import { NextResponse } from "next/server";
import { signoffMatrixForUi } from "@/lib/signoff";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const variant = url.searchParams.get("variant") ?? "flowlab";
  try {
    const matrix = signoffMatrixForUi(variant);
    return NextResponse.json(matrix);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: message },
      { status: message.startsWith("REFUSED:") ? 400 : 500 },
    );
  }
}

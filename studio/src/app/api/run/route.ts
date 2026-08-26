import { NextResponse } from "next/server";
import { isAllowedAction, runCourseAction } from "@/lib/run";

export const dynamic = "force-dynamic";
export const maxDuration = 900;

export async function POST(req: Request) {
  const body = (await req.json()) as { action?: string };
  const action = body.action ?? "";
  if (!isAllowedAction(action)) {
    return NextResponse.json(
      { error: `Azione non consentita. Usa: check, status, list, synth, floorplan, place, cts, route, finish, test_course` },
      { status: 400 },
    );
  }
  const result = await runCourseAction(action);
  return NextResponse.json(result, { status: result.ok ? 200 : 500 });
}

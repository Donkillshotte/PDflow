import { NextResponse } from "next/server";
import { markLessonComplete, readProgress, writeProgress, LESSONS } from "@/lib/course";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(readProgress());
}

export async function POST(req: Request) {
  const body = (await req.json()) as { lessonId?: string; action?: string };
  if (body.action === "reset") {
    writeProgress({
      started_at: new Date().toISOString(),
      completed_lessons: [],
      last_lesson: null,
      notes: [],
      updated_at: new Date().toISOString(),
    });
    return NextResponse.json(readProgress());
  }
  if (!body.lessonId || !LESSONS.some((l) => l.id === body.lessonId)) {
    return NextResponse.json({ error: "lessonId non valido" }, { status: 400 });
  }
  return NextResponse.json(markLessonComplete(body.lessonId));
}

import { NextResponse } from "next/server";
import {
  markLessonComplete,
  readProgress,
  writeProgress,
  updateLessonSteps,
  updateLabChecks,
  LESSONS,
} from "@/lib/course";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(readProgress());
}

export async function POST(req: Request) {
  const body = (await req.json()) as {
    lessonId?: string;
    action?: string;
    steps?: string[];
    checks?: string[];
  };

  if (body.action === "reset") {
    writeProgress({
      started_at: new Date().toISOString(),
      completed_lessons: [],
      last_lesson: null,
      notes: [],
      lesson_steps: {},
      lab_checks: {},
      updated_at: new Date().toISOString(),
    });
    return NextResponse.json(readProgress());
  }

  if (!body.lessonId || !LESSONS.some((l) => l.id === body.lessonId)) {
    return NextResponse.json({ error: "lessonId non valido" }, { status: 400 });
  }

  if (body.action === "steps" && Array.isArray(body.steps)) {
    return NextResponse.json(updateLessonSteps(body.lessonId, body.steps));
  }
  if (body.action === "checks" && Array.isArray(body.checks)) {
    return NextResponse.json(updateLabChecks(body.lessonId, body.checks));
  }

  return NextResponse.json(markLessonComplete(body.lessonId));
}

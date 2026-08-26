import { NextResponse } from "next/server";
import {
  LESSONS,
  extractLabChecklist,
  readLessonFile,
  readProgress,
  writeProgress,
  updateLessonSteps,
  updateLabChecks,
  markLessonComplete,
} from "@/lib/course";
import { evaluateLessonGates } from "@/lib/jobs";

export const dynamic = "force-dynamic";

function gatesFor(lessonId: string) {
  const lesson = LESSONS.find((l) => l.id === lessonId);
  if (!lesson) return null;
  const progress = readProgress();
  const lab = readLessonFile(lessonId, "LAB.md") ?? "";
  const checklist = extractLabChecklist(lab);
  return evaluateLessonGates({
    lessonId,
    makeTarget: lesson.makeTarget,
    steps: progress.lesson_steps?.[lessonId] ?? [],
    checks: progress.lab_checks?.[lessonId] ?? [],
    checklistSize: checklist.length,
  });
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const lessonId = url.searchParams.get("lessonId");
  const progress = readProgress();
  if (lessonId) {
    const gates = gatesFor(lessonId);
    if (!gates) {
      return NextResponse.json({ error: "lessonId non valido" }, { status: 400 });
    }
    return NextResponse.json({ progress, gates });
  }
  return NextResponse.json(progress);
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

  if (body.action === "gates" && body.lessonId) {
    const gates = gatesFor(body.lessonId);
    if (!gates) {
      return NextResponse.json({ error: "lessonId non valido" }, { status: 400 });
    }
    return NextResponse.json(gates);
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

  // Hard completion gate — reject if requirements not met
  const gates = gatesFor(body.lessonId)!;
  if (!gates.ok) {
    return NextResponse.json(
      {
        error: "Gate di completamento non soddisfatti",
        code: "gates",
        gates: gates.gates,
      },
      { status: 422 },
    );
  }

  return NextResponse.json(markLessonComplete(body.lessonId));
}

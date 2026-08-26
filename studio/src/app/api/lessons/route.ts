import { NextResponse } from "next/server";
import { LESSONS, readProgress } from "@/lib/course";

export const dynamic = "force-dynamic";

export async function GET() {
  const progress = readProgress();
  const done = new Set(progress.completed_lessons ?? []);
  return NextResponse.json({
    lessons: LESSONS.map((l) => ({
      ...l,
      completed: done.has(l.id),
    })),
    progress,
  });
}

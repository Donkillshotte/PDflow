import { NextResponse } from "next/server";
import { LESSONS, readLessonFile } from "@/lib/course";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const meta = LESSONS.find((l) => l.id === id);
  if (!meta) {
    return NextResponse.json({ error: "Lesson not found" }, { status: 404 });
  }
  return NextResponse.json({
    ...meta,
    readme: readLessonFile(id, "README.md"),
    lab: readLessonFile(id, "LAB.md"),
    runSh: readLessonFile(id, "run.sh"),
  });
}

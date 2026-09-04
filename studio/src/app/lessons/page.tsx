import Link from "next/link";
import { SurfaceRail } from "@/components/SurfaceRail";
import { LESSONS, readProgress } from "@/lib/course";

export const dynamic = "force-dynamic";

export default function LessonsPage() {
  const progress = readProgress();
  const done = new Set(progress.completed_lessons ?? []);

  return (
    <main>
      <SurfaceRail />
      <header className="page-head">
        <h1>Lessons</h1>
        <p>
          Eight steps from constraints to GDS on Nangate45. Student pace stays
          0/8 until you mark a lesson. FlowLab leftover stays named on finish.
        </p>
      </header>
      <div className="lesson-grid">
        {LESSONS.map((l, i) => (
          <Link
            key={l.id}
            href={`/lessons/${l.id}`}
            className={`lesson-item${done.has(l.id) ? " done" : ""}`}
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <div className="lesson-num">LESSON {l.num}</div>
            <h2>{l.title}</h2>
            <p>{l.blurb}</p>
            <div className="lesson-meta">
              <span className="pill">{l.duration}</span>
              <span className="pill">{l.stage}</span>
              {done.has(l.id) && <span className="pill ok">completed</span>}
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}

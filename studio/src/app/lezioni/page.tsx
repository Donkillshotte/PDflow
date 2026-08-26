import Link from "next/link";
import { LESSONS, readProgress } from "@/lib/course";

export const dynamic = "force-dynamic";

export default function LessonsPage() {
  const progress = readProgress();
  const done = new Set(progress.completed_lessons ?? []);

  return (
    <main>
      <header className="page-head">
        <h1>Lezioni</h1>
        <p>
          Otto tappe da constraints a GDS. Apri teoria e LAB, lancia le fasi ORFS
          dalla UI, segna il progresso quando hai finito.
        </p>
      </header>
      <div className="lesson-grid">
        {LESSONS.map((l, i) => (
          <Link
            key={l.id}
            href={`/lezioni/${l.id}`}
            className={`lesson-item${done.has(l.id) ? " done" : ""}`}
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <div className="lesson-num">LEZIONE {l.num}</div>
            <h2>{l.title}</h2>
            <p>{l.blurb}</p>
            <div className="lesson-meta">
              <span className="pill">{l.duration}</span>
              <span className="pill">{l.stage}</span>
              {done.has(l.id) && <span className="pill ok">completata</span>}
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}

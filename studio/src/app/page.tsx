import Link from "next/link";
import { LESSONS, readProgress } from "@/lib/course";

export const dynamic = "force-dynamic";

export default function HomePage() {
  const progress = readProgress();
  const done = new Set(progress.completed_lessons ?? []);
  const completed = done.size;
  const next =
    LESSONS.find((l) => !done.has(l.id)) ?? LESSONS[LESSONS.length - 1];

  return (
    <main>
      <section className="hero">
        <div className="hero-metal" aria-hidden />
        <div className="hero-glow" aria-hidden />
        <div className="hero-copy">
          <p className="hero-brand">OpenROAD</p>
          <h1 className="hero-title">Physical Design, senza script da ricordare</h1>
          <p className="hero-lead">
            Studio interattivo sul flusso RTL→GDS: lezioni, materiali e comandi ORFS
            da un’unica interfaccia.
          </p>
          <div className="cta-row">
            <Link href={`/lezioni/${next.id}`} className="btn-primary">
              Continua · {next.title}
            </Link>
            <Link href="/strumenti" className="btn-ghost">
              Controlla toolchain
            </Link>
          </div>
          <div className="progress-strip" aria-label={`Progresso ${completed} su 8`}>
            {LESSONS.map((l) => (
              <span
                key={l.id}
                className={`progress-dot${done.has(l.id) ? " on" : ""}`}
                title={l.title}
              />
            ))}
          </div>
          <p className="footer-note">
            {completed}/8 lezioni segnate · ultima: {progress.last_lesson ?? "—"}
          </p>
        </div>
      </section>
    </main>
  );
}

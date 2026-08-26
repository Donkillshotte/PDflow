"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { MarkdownView } from "@/components/MarkdownView";
import { RunConsole } from "@/components/RunConsole";

type LessonPayload = {
  id: string;
  num: string;
  title: string;
  duration: string;
  stage: string;
  blurb: string;
  makeTarget: string;
  readme: string | null;
  lab: string | null;
};

type Tab = "teoria" | "lab" | "esegui";

export default function LessonDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [lesson, setLesson] = useState<LessonPayload | null>(null);
  const [tab, setTab] = useState<Tab>("teoria");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [lRes, pRes] = await Promise.all([
        fetch(`/api/lessons/${id}`),
        fetch("/api/progress"),
      ]);
      if (!lRes.ok) {
        setError("Lezione non trovata");
        return;
      }
      const data = (await lRes.json()) as LessonPayload;
      const progress = await pRes.json();
      if (!cancelled) {
        setLesson(data);
        setDone((progress.completed_lessons ?? []).includes(id));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function markDone() {
    const res = await fetch("/api/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lessonId: id }),
    });
    if (res.ok) setDone(true);
  }

  if (error) {
    return (
      <main>
        <header className="page-head">
          <h1>Errore</h1>
          <p>{error}</p>
        </header>
      </main>
    );
  }

  if (!lesson) {
    return (
      <main>
        <header className="page-head">
          <h1>Caricamento…</h1>
        </header>
      </main>
    );
  }

  return (
    <main>
      <header className="page-head">
        <div className="lesson-num">LEZIONE {lesson.num}</div>
        <h1>{lesson.title}</h1>
        <p>
          {lesson.blurb} · {lesson.duration} · fase ORFS <code>{lesson.makeTarget}</code>
        </p>
      </header>

      <div className="lesson-actions">
        <Link href="/lezioni" className="btn-ghost">
          ← Tutte le lezioni
        </Link>
        <button type="button" className="btn-primary" onClick={markDone} disabled={done}>
          {done ? "Già completata" : "Segna come completata"}
        </button>
        {done && <span className="pill ok">nel progresso</span>}
      </div>

      <div className="tabs" role="tablist">
        {(
          [
            ["teoria", "Teoria"],
            ["lab", "Laboratorio"],
            ["esegui", "Esegui fase"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            className={`tab${tab === key ? " tab-active" : ""}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      <section className="panel">
        {tab === "teoria" && lesson.readme && (
          <MarkdownView content={lesson.readme} basePath={`lessons/${id}`} />
        )}
        {tab === "lab" && lesson.lab && (
          <MarkdownView content={lesson.lab} basePath={`lessons/${id}`} />
        )}
        {tab === "esegui" && (
          <div>
            <p style={{ color: "var(--ink-soft)", marginTop: 0 }}>
              Lancia il target ORFS della lezione (<strong>{lesson.makeTarget}</strong>)
              con <code>FLOW_VARIANT=learn</code>. Synth è rapido; route/finish possono
              richiedere diversi minuti.
            </p>
            <RunConsole defaultAction={lesson.makeTarget} compact />
          </div>
        )}
      </section>
    </main>
  );
}

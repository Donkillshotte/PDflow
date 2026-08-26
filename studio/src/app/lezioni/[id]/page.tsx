"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { LessonWizard } from "@/components/LessonWizard";

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

export default function LessonDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [lesson, setLesson] = useState<LessonPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetch(`/api/lessons/${id}`);
      if (!res.ok) {
        setError("Lezione non trovata");
        return;
      }
      const data = (await res.json()) as LessonPayload;
      if (!cancelled) setLesson(data);
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) {
    return (
      <main>
        <header className="page-head">
          <h1>Errore</h1>
          <p>{error}</p>
          <Link href="/lezioni" className="btn-ghost">
            ← Lezioni
          </Link>
        </header>
      </main>
    );
  }

  if (!lesson) {
    return (
      <main>
        <header className="page-head">
          <h1 className="skeleton-line">Caricamento lezione…</h1>
          <p className="muted">Preparazione percorso guidato</p>
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
          Percorso guidato · {lesson.duration} · fase{" "}
          <code>{lesson.makeTarget}</code>
        </p>
        <p className="hero-lead" style={{ marginBottom: 0 }}>
          {lesson.blurb}
        </p>
      </header>
      <div className="lesson-actions">
        <Link href="/lezioni" className="btn-ghost">
          ← Tutte le lezioni
        </Link>
      </div>
      <LessonWizard lesson={lesson} />
    </main>
  );
}

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
        setError("Lesson not found");
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
          <h1>Error</h1>
          <p>{error}</p>
          <Link href="/lessons" className="btn-ghost">
            ← Lessons
          </Link>
        </header>
      </main>
    );
  }

  if (!lesson) {
    return (
      <main>
        <header className="page-head">
          <h1 className="skeleton-line">Loading lesson…</h1>
          <p className="muted">Preparing guided path</p>
        </header>
      </main>
    );
  }

  return (
    <main>
      <header className="page-head">
        <div className="lesson-num">LESSON {lesson.num}</div>
        <h1>{lesson.title}</h1>
        <p>
          Guided path · {lesson.duration} · phase{" "}
          <code>{lesson.makeTarget}</code>
        </p>
        <p className="hero-lead" style={{ marginBottom: 0 }}>
          {lesson.blurb}
        </p>
      </header>
      <div className="lesson-actions">
        <Link href="/lessons" className="btn-ghost">
          ← All lessons
        </Link>
      </div>
      <LessonWizard lesson={lesson} />
    </main>
  );
}

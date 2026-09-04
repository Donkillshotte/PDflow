"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { LeftoverSuiteStrip } from "@/components/LeftoverSuiteStrip";
import { LessonWizard } from "@/components/LessonWizard";
import { SurfaceRail } from "@/components/SurfaceRail";

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
        <SurfaceRail />
        <header className="page-head">
          <h1>Error</h1>
          <p>{error}</p>
          <p className="muted">
            Leftover named stays on{" "}
            <Link href="/flow?phase=finish#signoff">finish signoff</Link>, not
            on this lesson path.
          </p>
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
        <SurfaceRail />
        <header className="page-head">
          <h1 className="skeleton-line">Loading lesson…</h1>
          <p className="muted">Preparing guided path</p>
        </header>
      </main>
    );
  }

  return (
    <main>
      <SurfaceRail />
      <header className="page-head">
        <div className="lesson-num">LESSON {lesson.num}</div>
        <h1>{lesson.title}</h1>
        <p>
          Guided path · {lesson.duration} · phase{" "}
          <code>{lesson.makeTarget}</code>
        </p>
        <p className="hero-lead">
          {lesson.blurb}
        </p>
        <p className="muted">
          Student pace stays 0/8 until you mark a lesson. Leftover named
          (setup, DFF_X2, no MCMM, no density) stays on{" "}
          <Link href="/flow?phase=finish#signoff">finish signoff</Link>, not
          on this guided path.
        </p>
        <LeftoverSuiteStrip compact href="/flow?phase=finish#signoff" />
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

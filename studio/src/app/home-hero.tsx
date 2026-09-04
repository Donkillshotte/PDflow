"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Lesson = {
  id: string;
  num: string;
  title: string;
  completed: boolean;
  makeTarget: string;
};

export function HomeHero() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [ready, setReady] = useState<boolean | null>(null);

  useEffect(() => {
    void Promise.all([
      fetch("/api/lessons").then((r) => r.json()),
      fetch("/api/toolchain").then((r) => r.json()),
    ]).then(([L, T]) => {
      setLessons(L.lessons ?? []);
      setReady(Boolean(T.ready));
    });
  }, []);

  const completed = lessons.filter((l) => l.completed).length;
  const next = lessons.find((l) => !l.completed) ?? lessons[lessons.length - 1];

  return (
    <section className="hero">
      <div className="hero-metal" aria-hidden />
      <div className="hero-glow" aria-hidden />
      <div className="hero-copy">
        <p className="hero-brand">OpenROAD</p>
        <h1 className="hero-title">RTL → GDS on OpenROAD</h1>
        <p className="hero-lead">
          Nangate45 / FreePDK45. Signoff is STA → DRC → LVS → power.
          Leftover stays named. DSE proposes knobs; wins stay in{" "}
          <code>win_rule.py</code>.
        </p>
        <div className="cta-row">
          <Link href="/flow" className="btn-primary">
            Open FlowLab
          </Link>
          {next ? (
            <Link href={`/lessons/${next.id}`} className="btn-ghost">
              Course · {next.title}
            </Link>
          ) : (
            <Link href="/lessons" className="btn-ghost">
              Open lessons
            </Link>
          )}
          <Link href="/tools" className="btn-ghost">
            Tools
          </Link>
        </div>
        <div className="progress-strip" aria-label={`Progress ${completed} of 8`}>
          {lessons.map((l) => (
            <Link
              key={l.id}
              href={`/lessons/${l.id}`}
              className={`progress-dot${l.completed ? " on" : ""}`}
              title={l.title}
            />
          ))}
        </div>
        <p className="footer-note">
          {completed}/8 lessons · toolchain{" "}
          {ready === null ? "…" : ready ? "ready" : "needs setup"}
        </p>
      </div>
    </section>
  );
}

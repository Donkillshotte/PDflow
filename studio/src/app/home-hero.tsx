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
    ])
      .then(([L, T]) => {
        setLessons(L.lessons ?? []);
        setReady(Boolean(T.ready));
      })
      .catch(() => {
        // The overview remains usable while the local agent is starting.
        setReady(null);
      });
  }, []);

  const completed = lessons.filter((l) => l.completed).length;
  const next = lessons.find((l) => !l.completed) ?? lessons[lessons.length - 1];

  return (
    <section className="overview-command-bar" aria-labelledby="overview-title">
      <div className="overview-command-copy">
        <p className="studio-pro-eyebrow">PDflow / Overview</p>
        <h1 id="overview-title">Current workspace</h1>
        <p>
          gcd · nangate45 · Linux local agent. Resume from the live FlowLab
          context, inspect the current finish, or open the native tool registry.
        </p>
        <div className="cta-row">
          <Link href="/flow?phase=rtl" className="btn-primary">
            Resume FlowLab
          </Link>
          {next ? (
            <Link href={`/lessons/${next.id}`} className="btn-ghost">
              Next lesson · {next.title}
            </Link>
          ) : (
            <Link href="/lessons" className="btn-ghost">
              Open lessons
            </Link>
          )}
          <Link href="/tools?tab=suite#suite" className="btn-ghost">
            Tool registry
          </Link>
        </div>
      </div>
      <div className="overview-command-stats" aria-label="Workspace status">
        <div>
          <span>Course progress</span>
          <strong>{completed}/8</strong>
          <small>lessons completed</small>
        </div>
        <div>
          <span>Native toolchain</span>
          <strong>{ready === null ? "…" : ready ? "READY" : "GAP"}</strong>
          <small>local capability probe</small>
        </div>
        <div>
          <span>Product boundary</span>
          <strong>FINISH</strong>
          <small>read-only · candidate for edits</small>
        </div>
      </div>
    </section>
  );
}

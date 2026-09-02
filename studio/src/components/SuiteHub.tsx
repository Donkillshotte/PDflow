"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";

type Hook = {
  id: string;
  label: string;
  group: string;
  ok: boolean;
  detail: string;
  action?: string;
  href?: string;
};

type Suite = {
  ready: boolean;
  summary: {
    hooksOk: number;
    hooksTotal: number;
    lessonsDone: number;
    lessonsTotal: number;
    viewerRunning: boolean;
    recentJobs: number;
    pipelineReady: number;
  };
  hooks: Hook[];
};

export function SuiteHub({ compact }: { compact?: boolean }) {
  const [data, setData] = useState<Suite | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch("/api/suite");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(id);
  }, [load]);

  if (error) {
    return (
      <div className="suite-hub">
        <p className="block-banner">{error}</p>
        <button type="button" className="btn-ghost" onClick={load}>
          Retry
        </button>
      </div>
    );
  }
  if (!data) {
    return <div className="suite-hub muted">Loading suite status…</div>;
  }

  const groups = Array.from(new Set(data.hooks.map((h) => h.group)));

  return (
    <div className={clsx("suite-hub", compact && "suite-hub-compact")}>
      <div className="ops-head">
        <div>
          <h2>Collaborative suite</h2>
          <p className="muted">
            Hook wrapper · {data.summary.hooksOk}/{data.summary.hooksTotal} ok ·
            lessons {data.summary.lessonsDone}/{data.summary.lessonsTotal} ·
            pipeline {data.summary.pipelineReady}/6 · recent jobs{" "}
            {data.summary.recentJobs}
            {data.summary.viewerRunning ? " · web viewer ON" : ""}
          </p>
        </div>
        <div className="lesson-actions">
          <span className={clsx("pill", data.ready ? "ok" : "bad")}>
            {data.ready ? "core wired" : "gap core"}
          </span>
          <button type="button" className="btn-ghost" onClick={load}>
            Refresh
          </button>
          <Link href="/materiali/reference/extended-flow.md" className="btn-ghost">
            Flow map
          </Link>
        </div>
      </div>

      {groups.map((g) => (
        <div key={g} className="suite-group">
          <h3>{g}</h3>
          <ul className="suite-hooks">
            {data.hooks
              .filter((h) => h.group === g)
              .map((h) => (
                <li key={h.id} className={h.ok ? "ok" : "bad"}>
                  <div>
                    <strong>{h.label}</strong>
                    <em>{h.detail}</em>
                  </div>
                  <div className="suite-hook-actions">
                    <span className={clsx("pill", h.ok ? "ok" : "bad")}>
                      {h.ok ? "ok" : "gap"}
                    </span>
                    {h.href && (
                      <Link href={h.href} className="btn-ghost btn-tiny">
                        Open
                      </Link>
                    )}
                    {h.action && (
                      <Link
                        href={`/strumenti?tab=run&action=${h.action}`}
                        className="btn-ghost btn-tiny"
                      >
                        Run
                      </Link>
                    )}
                  </div>
                </li>
              ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

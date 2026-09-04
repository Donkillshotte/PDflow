"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { LeftoverChips, StatusTone } from "@/components/LeftoverChips";
import { hookVisualState } from "@/lib/leftoverUi";

type Hook = {
  id: string;
  label: string;
  group: string;
  ok: boolean;
  detail: string;
  action?: string;
  href?: string;
  leftover?: { ids: string[] };
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

export function SuiteHub() {
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
    <div className="suite-hub">
      <div className="ops-head">
        <div>
          <h2>Toolchain hook matrix</h2>
          <p className="muted">
            Environment, course artifacts, FlowLab reports, and product cooks
            stay on their own contracts. A green hook can still name leftover
            · {data.summary.hooksOk}/{data.summary.hooksTotal} ok · leftover
            named on signoff · lessons {data.summary.lessonsDone}/
            {data.summary.lessonsTotal} · pipeline {data.summary.pipelineReady}
            /6 · recent jobs {data.summary.recentJobs}
            {data.summary.viewerRunning ? " · web viewer on" : ""}
            {" · "}
            <Link href="/#story">story</Link>
          </p>
        </div>
        <div className="lesson-actions">
          <span className={clsx("pill", data.ready ? "ok" : "bad")}>
            {data.ready ? "core wired" : "gap core"}
          </span>
          <button type="button" className="btn-ghost" onClick={load}>
            Refresh
          </button>
          <Link href="/materials/reference/extended-flow.md" className="btn-ghost">
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
              .map((h) => {
                const state = hookVisualState(h.ok, h.leftover?.ids);
                return (
                <li key={h.id} className={clsx(h.ok ? "ok" : "bad", state === "leftover" && "leftover")}>
                  <div>
                    <strong>{h.label}</strong>
                    <em>{h.detail}</em>
                    <LeftoverChips ids={h.leftover?.ids} detail={h.detail} compact />
                  </div>
                  <div className="suite-hook-actions">
                    <StatusTone state={state} />
                    {h.href && (
                      <Link href={h.href} className="btn-ghost btn-tiny">
                        Open
                      </Link>
                    )}
                    {h.action && h.href !== "/lab" && h.href !== "/pkg" && (
                      <Link
                        href={`/tools?tab=run&action=${h.action}`}
                        className="btn-ghost btn-tiny"
                      >
                        Run
                      </Link>
                    )}
                  </div>
                </li>
                );
              })}
          </ul>
        </div>
      ))}
    </div>
  );
}

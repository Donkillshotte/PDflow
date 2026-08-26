"use client";

import clsx from "clsx";

export type PhaseRun = {
  id: string;
  action: string;
  status: string;
  startedAt: string;
  ms?: number;
};

export function FlowLabPhaseHistory({
  phaseLabel,
  runs,
  loading,
}: {
  phaseLabel: string;
  runs: PhaseRun[];
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="fl-phase-history fl-phase-history-loading" aria-busy="true">
        <span className="fl-pulse">Carico storico {phaseLabel}…</span>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="fl-phase-history fl-phase-history-empty">
        <span>Nessuna run registrata per {phaseLabel}</span>
      </div>
    );
  }

  return (
    <div className="fl-phase-history">
      <div className="fl-phase-history-head">
        <strong>Storico run · {phaseLabel}</strong>
        <span>{runs.length} recenti</span>
      </div>
      <ul className="fl-phase-history-list">
        {runs.map((r) => (
          <li key={r.id}>
            <span
              className={clsx(
                "fl-run-dot",
                r.status === "ok" && "ok",
                r.status === "error" && "bad",
                r.status === "running" && "run",
              )}
            />
            <div>
              <code>{r.id.slice(0, 8)}</code>
              <em>{new Date(r.startedAt).toLocaleString()}</em>
            </div>
            <span className="fl-run-status">
              {r.status}
              {r.ms != null ? ` · ${Math.round(r.ms / 1000)}s` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";

type PipelineRow = {
  stage: string;
  ready: boolean;
  artifactCount: number;
  artifactReady: number;
  depsMet: boolean;
  dep: string | null;
  lastJob: {
    id: string;
    status: string;
    finishedAt?: string;
    ms?: number;
  } | null;
};

type JobRow = {
  id: string;
  action: string;
  status: string;
  startedAt: string;
  finishedAt?: string;
  ms?: number;
  code?: number | null;
  command: string;
  logTail: string;
};

type JobsPayload = {
  jobs: JobRow[];
  lock: { jobId: string; action: string; startedAt: string } | null;
  pipeline: PipelineRow[];
};

function formatMs(ms?: number) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function OpsDashboard({ refreshKey = 0 }: { refreshKey?: number }) {
  const [data, setData] = useState<JobsPayload | null>(null);
  const [selected, setSelected] = useState<JobRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/jobs?limit=25");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function forceUnlock() {
    await fetch("/api/jobs?force=1", { method: "DELETE" });
    await load();
  }

  function exportLog(job: JobRow) {
    const blob = new Blob([job.logTail || "(vuoto)"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `job-${job.action}-${job.id.slice(0, 8)}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="ops-dash">
      <div className="ops-head">
        <div>
          <h2>Pipeline &amp; job</h2>
          <p className="muted">
            Stato artefatti, dipendenze tra fasi, storico run e lock attivo.
          </p>
        </div>
        <div className="lesson-actions">
          <button type="button" className="btn-ghost" onClick={load} disabled={loading}>
            {loading ? "Aggiorno…" : "Aggiorna"}
          </button>
          {data?.lock && (
            <button type="button" className="btn-danger" onClick={forceUnlock}>
              Forza unlock
            </button>
          )}
        </div>
      </div>

      {error && <p className="empty-hint bad-text">{error}</p>}

      {data?.lock && (
        <div className="lock-banner" role="status">
          Lock attivo: <strong>{data.lock.action}</strong> · job{" "}
          <code>{data.lock.jobId.slice(0, 8)}…</code> · da {data.lock.startedAt}
        </div>
      )}

      <ol className="pipeline-track" aria-label="Stato pipeline">
        {(data?.pipeline ?? []).map((row) => (
          <li
            key={row.stage}
            className={clsx(
              "pipeline-node",
              row.ready && "ready",
              !row.depsMet && "blocked",
            )}
          >
            <strong>{row.stage}</strong>
            <span>
              {row.artifactReady}/{row.artifactCount} art.
            </span>
            <span className="muted">
              {row.depsMet
                ? row.ready
                  ? "pronto"
                  : "eseguibile"
                : `attende ${row.dep}`}
            </span>
            {row.lastJob && (
              <em className={clsx("pill", row.lastJob.status === "ok" ? "ok" : "bad")}>
                {row.lastJob.status}
              </em>
            )}
          </li>
        ))}
      </ol>

      <div className="job-table-wrap">
        <table className="job-table">
          <caption>Storico job (ultimi 25)</caption>
          <thead>
            <tr>
              <th scope="col">Azione</th>
              <th scope="col">Stato</th>
              <th scope="col">Durata</th>
              <th scope="col">Inizio</th>
              <th scope="col">Azioni</th>
            </tr>
          </thead>
          <tbody>
            {(data?.jobs ?? []).length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  Nessun job ancora — lancia una fase dalla console.
                </td>
              </tr>
            )}
            {(data?.jobs ?? []).map((j) => (
              <tr key={j.id} className={selected?.id === j.id ? "selected" : undefined}>
                <td>
                  <code>{j.action}</code>
                </td>
                <td>
                  <span
                    className={clsx(
                      "pill",
                      j.status === "ok" && "ok",
                      (j.status === "error" || j.status === "cancelled") && "bad",
                      j.status === "running" && "live",
                    )}
                  >
                    {j.status}
                  </span>
                </td>
                <td>{formatMs(j.ms)}</td>
                <td className="mono-hint">{j.startedAt.replace("T", " ").slice(0, 19)}</td>
                <td className="job-row-actions">
                  <button type="button" className="btn-ghost btn-tiny" onClick={() => setSelected(j)}>
                    Dettaglio
                  </button>
                  <button type="button" className="btn-ghost btn-tiny" onClick={() => exportLog(j)}>
                    Export log
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <aside className="job-detail panel" aria-label="Dettaglio job">
          <header className="ops-head">
            <div>
              <h3>
                {selected.action} · <code>{selected.id.slice(0, 8)}</code>
              </h3>
              <p className="mono-hint">{selected.command}</p>
            </div>
            <button type="button" className="btn-ghost" onClick={() => setSelected(null)}>
              Chiudi
            </button>
          </header>
          <pre className="run-log">{selected.logTail || "(log vuoto)"}</pre>
        </aside>
      )}
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";

type Artifact = {
  name: string;
  exists: boolean;
  size: number;
  mtime: string | null;
};

type Metric = { label: string; value: string; source: string };
type Golden = { label: string; value: string };

type Results = {
  stage: string;
  artifacts: Artifact[];
  metrics: Metric[];
  goldenHints: Golden[];
};

function fmtSize(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

export function ResultsPanel({
  stage,
  refreshKey,
}: {
  stage: string;
  refreshKey?: number;
}) {
  const [data, setData] = useState<Results | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/results?stage=${encodeURIComponent(stage)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "errore");
    } finally {
      setLoading(false);
    }
  }, [stage]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  if (loading && !data) {
    return <div className="results-panel muted">Carico artefatti…</div>;
  }
  if (error) {
    return (
      <div className="results-panel">
        <p className="pill bad">{error}</p>
        <button type="button" className="btn-ghost" onClick={load}>
          Riprova
        </button>
      </div>
    );
  }
  if (!data) return null;

  const ready = data.artifacts.filter((a) => a.exists).length;
  const total = data.artifacts.length;

  return (
    <div className="results-panel">
      <div className="results-head">
        <h3>Risultati · {stage}</h3>
        <button type="button" className="btn-ghost" onClick={load}>
          Aggiorna
        </button>
      </div>

      {total > 0 && (
        <>
          <p className="muted">
            Artefatti: <strong>{ready}/{total}</strong> presenti in{" "}
            <code>results/.../learn/</code>
          </p>
          <ul className="artifact-list">
            {data.artifacts.map((a) => (
              <li key={a.name} className={a.exists ? "on" : "off"}>
                <span className={`dot ${a.exists ? "ok" : "bad"}`} />
                <code>{a.name}</code>
                <em>
                  {a.exists
                    ? `${fmtSize(a.size)}${a.mtime ? ` · ${new Date(a.mtime).toLocaleString()}` : ""}`
                    : "mancante"}
                </em>
              </li>
            ))}
          </ul>
        </>
      )}

      {data.metrics.length > 0 && (
        <div className="metric-block">
          <h4>Metriche dai tuoi report</h4>
          <ul className="metric-list">
            {data.metrics.map((m, i) => (
              <li key={`${m.source}-${i}`}>
                <code>{m.source}</code>
                <span>{m.value}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.goldenHints.length > 0 && (
        <div className="metric-block golden">
          <h4>
            Riferimento golden{" "}
            <a href="/materiali/reference/golden-metrics.md">apri tabella</a>
          </h4>
          <ul className="metric-list">
            {data.goldenHints.map((g) => (
              <li key={g.label}>
                <strong>{g.label}</strong>
                <span>{g.value}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {total > 0 && ready === 0 && (
        <p className="empty-hint">
          Nessun artefatto ancora: lancia la fase, poi premi Aggiorna.
        </p>
      )}
    </div>
  );
}

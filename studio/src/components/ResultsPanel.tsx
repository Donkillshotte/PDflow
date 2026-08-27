"use client";

import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/components/ToastProvider";

type Artifact = {
  name: string;
  exists: boolean;
  size: number;
  mtime: string | null;
};

type Metric = {
  label: string;
  value: string;
  source: string;
  expected?: boolean;
};
type Golden = { label: string; value: string };
type LogDigest = {
  errors: number;
  warnings: number;
  noiseWarnings: number;
  healthy: boolean;
  summary: string;
  noteworthy: { code: string; message: string; count: number }[];
  topCodes: { code: string; count: number; noise: boolean }[];
};

type Results = {
  stage: string;
  artifacts: Artifact[];
  metrics: Metric[];
  goldenHints: Golden[];
  logDigest?: LogDigest | null;
};

function fmtSize(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function canOpenExternally(name: string) {
  return /\.(odb|gds|oas)$/i.test(name);
}

export function ResultsPanel({
  stage,
  refreshKey,
  variant = "learn",
}: {
  stage: string;
  refreshKey?: number;
  variant?: string;
}) {
  const { push } = useToast();
  const [data, setData] = useState<Results | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/results?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "errore");
    } finally {
      setLoading(false);
    }
  }, [stage, variant]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function openArtifact(name: string) {
    setBusy(name);
    try {
      const res = await fetch("/api/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ artifact: name, variant }),
      });
      const body = await res.json();
      if (body.launched) {
        push(body.message || `Aperto ${name}`, "ok");
      } else if (body.command) {
        await navigator.clipboard?.writeText(body.command).catch(() => undefined);
        push(body.message || "Comando copiato — apri Desktop", "info");
      } else {
        push(body.message || body.error || "Apertura fallita", "bad");
      }
    } finally {
      setBusy(null);
    }
  }

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
    <div className="results-panel" id="results-panel">
      <div className="results-head">
        <h3>Risultati · {stage}</h3>
        <div className="lesson-actions">
          <a className="btn-ghost btn-tiny" href={`/strumenti?stage=${stage}&tab=results`}>
            Permalink
          </a>
          <button type="button" className="btn-ghost" onClick={load}>
            Aggiorna
          </button>
        </div>
      </div>

      {total > 0 && (
        <>
          <p className="muted">
            Artefatti: <strong>{ready}/{total}</strong> — Apri ODB in OpenROAD o
            GDS in KLayout (Desktop).
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
                {a.exists && canOpenExternally(a.name) && (
                  <button
                    type="button"
                    className="btn-ghost btn-tiny"
                    disabled={busy === a.name}
                    onClick={() => void openArtifact(a.name)}
                  >
                    {busy === a.name ? "…" : "Apri GUI"}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {data.logDigest && (
        <div
          className={`metric-block ${data.logDigest.healthy ? "digest-ok" : "digest-bad"}`}
        >
          <h4>Diagnosi log ORFS</h4>
          <p className="muted">{data.logDigest.summary}</p>
          {data.logDigest.topCodes.length > 0 && (
            <ul className="metric-list">
              {data.logDigest.topCodes.map((c) => (
                <li key={c.code}>
                  <code>{c.code}</code>
                  <span>
                    ×{c.count}
                    {c.noise ? " · rumore atteso" : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {data.logDigest.noteworthy.length > 0 && (
            <p className="muted">
              Note: {data.logDigest.noteworthy.map((n) => n.code).join(", ")} —
              su GCD nangate45 un WNS≈−0.04 con qualche setup violation è il
              golden del corso, non un bug del wrapper.
            </p>
          )}
        </div>
      )}

      {data.metrics.length > 0 && (
        <div className="metric-block">
          <h4>Metriche dai tuoi report</h4>
          <ul className="metric-list">
            {data.metrics.map((m, i) => (
              <li key={`${m.source}-${i}`}>
                <code>{m.source}</code>
                <span>
                  {m.value}
                  {m.expected ? " · atteso (golden)" : ""}
                </span>
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

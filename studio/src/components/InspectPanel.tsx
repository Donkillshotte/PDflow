"use client";

import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/components/ToastProvider";

type Inspect = {
  stage: string;
  odb: {
    design: string;
    instances: number;
    nets: number;
    dieDbu: { dx: number; dy: number };
    artifact: string;
  } | null;
  sta: {
    source: string;
    wns?: string;
    tns?: string;
    worstSlack?: string;
    paths: { endpoint: string; slack: string; status: string }[];
    jsonPaths?: number;
  } | null;
  yosys: {
    cells?: string;
    area?: string;
    dff?: string;
    rawHits: string[];
  } | null;
  hooks: { id: string; label: string; detail: string }[];
};

export function InspectPanel({
  stage,
  refreshKey,
  variant = "learn",
}: {
  stage: string;
  refreshKey?: number;
  variant?: string;
}) {
  const { push } = useToast();
  const [data, setData] = useState<Inspect | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [viewerBusy, setViewerBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/inspect?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [stage, variant]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    void fetch("/api/viewer")
      .then((r) => r.json())
      .then((d) => {
        if (d.running && d.url) setViewerUrl(d.url);
      })
      .catch(() => undefined);
  }, []);

  async function startWeb() {
    setViewerBusy(true);
    try {
      const res = await fetch("/api/viewer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "start", stage, variant }),
      });
      const body = await res.json();
      if (body.ok && body.url) {
        setViewerUrl(body.url);
        push(body.message, "ok");
        // give server a moment to bind
        window.setTimeout(() => {
          window.open(body.url, "_blank", "noopener,noreferrer");
        }, 800);
      } else {
        push(body.message || "Viewer not started", "bad");
      }
    } finally {
      setViewerBusy(false);
    }
  }

  async function stopWeb() {
    await fetch("/api/viewer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "stop" }),
    });
    setViewerUrl(null);
    push("Web viewer stopped", "info");
  }

  return (
    <div className="inspect-panel" id="inspect-panel">
      <div className="results-head">
        <h3>Inspection tool · {stage}</h3>
        <div className="lesson-actions">
          <button type="button" className="btn-ghost" onClick={load} disabled={loading}>
            {loading ? "Analyzing…" : "Recalculate"}
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => void startWeb()}
            disabled={viewerBusy}
          >
            {viewerBusy ? "Avvio…" : "Open Web Viewer"}
          </button>
          {viewerUrl && (
            <>
              <a className="btn-ghost" href={viewerUrl} target="_blank" rel="noreferrer">
                Open tab
              </a>
              <button type="button" className="btn-ghost" onClick={() => void stopWeb()}>
                Stop viewer
              </button>
            </>
          )}
        </div>
      </div>

      {error && <p className="block-banner">{error}</p>}
      {loading && !data && <p className="muted">Eseguo OpenROAD/OpenSTA/Yosys…</p>}

      {data?.odb && (
        <div className="metric-block">
          <h4>ODB · OpenROAD Python</h4>
          <ul className="metric-list">
            <li>
              <strong>design</strong>
              <span>{data.odb.design}</span>
            </li>
            <li>
              <strong>instances</strong>
              <span>{data.odb.instances}</span>
            </li>
            <li>
              <strong>nets</strong>
              <span>{data.odb.nets}</span>
            </li>
            <li>
              <strong>die (dbu)</strong>
              <span>
                {data.odb.dieDbu.dx} × {data.odb.dieDbu.dy}
              </span>
            </li>
            <li>
              <strong>file</strong>
              <span>
                <code>{data.odb.artifact}</code>
              </span>
            </li>
          </ul>
        </div>
      )}

      {data?.sta && (
        <div className="metric-block">
          <h4>Timing · OpenSTA</h4>
          <p className="muted" style={{ marginTop: 0 }}>
            {data.sta.source}
            {data.sta.jsonPaths != null ? ` · ${data.sta.jsonPaths} path JSON` : ""}
          </p>
          <ul className="metric-list">
            {data.sta.wns != null && (
              <li>
                <strong>WNS</strong>
                <span>{data.sta.wns}</span>
              </li>
            )}
            {data.sta.tns != null && (
              <li>
                <strong>TNS</strong>
                <span>{data.sta.tns}</span>
              </li>
            )}
            {data.sta.worstSlack != null && (
              <li>
                <strong>worst slack</strong>
                <span>{data.sta.worstSlack}</span>
              </li>
            )}
          </ul>
          {data.sta.paths.length > 0 && (
            <>
              <p className="muted">
                VIOLATED paths with WNS≈−0.04 ns on GCD nangate45 align with the
                course golden — they do not indicate a wrapper crash.
              </p>
              <ul className="path-list">
                {data.sta.paths.map((p) => (
                  <li key={p.endpoint}>
                    <code>{p.endpoint}</code>
                    <em className={p.status === "MET" ? "pill ok" : "pill warn"}>
                      {p.slack} · {p.status}
                    </em>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {data?.yosys && (
        <div className="metric-block">
          <h4>Netlist · Yosys stat</h4>
          <ul className="metric-list">
            {data.yosys.cells && (
              <li>
                <strong>cells</strong>
                <span>{data.yosys.cells}</span>
              </li>
            )}
            {data.yosys.area && (
              <li>
                <strong>area</strong>
                <span>{data.yosys.area}</span>
              </li>
            )}
            {data.yosys.dff && (
              <li>
                <strong>DFF_X1</strong>
                <span>{data.yosys.dff}</span>
              </li>
            )}
          </ul>
        </div>
      )}

      {data && !data.odb && !data.sta && !data.yosys && (
        <p className="empty-hint">
          No tool data yet — run the phase, then Recalculate.
        </p>
      )}

      {data?.hooks && (
        <details className="hooks-details">
          <summary>Available tool hooks</summary>
          <ul className="hook-list">
            {data.hooks.map((h) => (
              <li key={h.id}>
                <strong>{h.label}</strong>
                <span>{h.detail}</span>
              </li>
            ))}
          </ul>
          <p className="muted">
            Guide:{" "}
            <a href="/materiali/reference/tool-hooks.md">tool-hooks.md</a>
          </p>
        </details>
      )}
    </div>
  );
}

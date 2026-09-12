"use client";

import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/components/ToastProvider";
import { isStageInspect, type StageInspect } from "@/lib/inspect";

export function InspectPanel({
  stage,
  refreshKey,
  variant = "learn",
  runId,
}: {
  stage: string;
  refreshKey?: number;
  variant?: string;
  runId?: string | null;
}) {
  const { push } = useToast();
  const [data, setData] = useState<StageInspect | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMode, setLoadingMode] = useState<"cache" | "recalculate" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [viewerBusy, setViewerBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadingMode("recalculate");
    setError(null);
    try {
      const res = await fetch(
        `/api/inspect?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      if (!isStageInspect(body)) throw new Error("agent returned an invalid inspection payload");
      setData(body);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
      setLoadingMode(null);
    }
  }, [runId, stage, variant]);

  const loadCached = useCallback(async () => {
    setLoading(true);
    setLoadingMode("cache");
    setError(null);
    try {
      const res = await fetch(
        `/api/inspections?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`,
        { cache: "no-store" },
      );
      const body = (await res.json().catch(() => ({}))) as {
        inspection?: unknown;
        reason?: string;
      };
      if (!res.ok) {
        throw new Error(body.reason || `HTTP ${res.status}`);
      }
      setData(isStageInspect(body.inspection) ? body.inspection : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
      setLoadingMode(null);
    }
  }, [runId, stage, variant]);

  useEffect(() => {
    // Changing phase, run or artifact revision invalidates the displayed
    // snapshot, but opening the inspector must remain a read-only UI action.
    // Recalculate is the explicit user consent to start an EDA inspection job.
    setData(null);
    setError(null);
    void loadCached();
  }, [loadCached, refreshKey]);

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
        body: JSON.stringify({ action: "start", stage, variant, run_id: runId ?? undefined }),
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
    } catch (e) {
      push(e instanceof Error ? e.message : "Viewer could not be started", "bad");
    } finally {
      setViewerBusy(false);
    }
  }

  async function stopWeb() {
    try {
      const response = await fetch("/api/viewer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "stop" }),
      });
      if (!response.ok) throw new Error(`Viewer stop HTTP ${response.status}`);
      setViewerUrl(null);
      push("Web viewer stopped", "info");
    } catch (e) {
      push(e instanceof Error ? e.message : "Viewer could not be stopped", "bad");
    }
  }

  return (
    <div className="inspect-panel" id="inspect-panel">
      <div className="results-head">
        <h3>Inspection tool · {stage}</h3>
        <div className="lesson-actions">
          <button type="button" className="btn-ghost" onClick={load} disabled={loading}>
            {loadingMode === "recalculate" ? "Analyzing…" : "Recalculate"}
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => void startWeb()}
            disabled={viewerBusy}
          >
            {viewerBusy ? "Starting…" : "Open Web Viewer"}
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
      {loading && !data && (
        <p className="muted">
          {loadingMode === "cache"
            ? "Reading the cached inspection snapshot…"
            : "Running validated OpenROAD/OpenSTA/Yosys inspection…"}
        </p>
      )}
      {!loading && !data && !error && (
        <div className="inspect-empty-state">
          <strong>No cached inspection snapshot</strong>
          <p>Opening this panel never starts an EDA process. Use Recalculate to create a report for the selected phase and run.</p>
        </div>
      )}

      {data?.status && data.status !== "PASS" && (
        <p className="block-banner">
          {data.status} · {data.reason || "This inspection is not a valid PASS result."}
        </p>
      )}

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
              These are the selected variant&apos;s live STA paths. Review the
              current report and the path-level evidence before judging a
              violation; the gate is driven by this report only.
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
            <a href="/materials/reference/tool-hooks.md">tool-hooks.md</a>
          </p>
        </details>
      )}
    </div>
  );
}

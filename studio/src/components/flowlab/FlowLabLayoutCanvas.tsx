"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import {
  Columns2,
  Layers,
  Maximize2,
  Minimize2,
  Monitor,
  RefreshCw,
  SquareSplitHorizontal,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import {
  LayoutViewport,
  type LayoutViewportHandle,
  type ViewportMode,
} from "./LayoutViewport";

type LayoutPhaseId =
  | "rtl"
  | "synth"
  | "floorplan"
  | "pdn"
  | "place"
  | "cts"
  | "route"
  | "finish"
  | "pkg";

type GalleryItem = {
  file: string;
  title: string;
  caption: string;
  url: string;
};

type CompareItem = {
  id: string;
  label: string;
  left: { file: string; title: string; url: string };
  right: { file: string; title: string; url: string };
};

type LayerItem = {
  id: string;
  name: string;
  color: string;
  role: string;
  soloShot?: string;
  soloAvailable?: boolean;
};

type PreviewMeta = {
  label: string;
  layerHint?: string;
  odbExists: boolean;
  odb: string | null;
  imageUrl: string | null;
  image?: { source: string; rel: string } | null;
  physical: boolean;
  artifact?: {
    path: string;
    relativePath?: string | null;
    exists: boolean;
    bytes: number;
    modifiedAt: string | null;
    artifactId?: string;
    contentHash?: string | null;
    authority?: string;
    mutable?: boolean;
    runId?: string | null;
    revision: number | string | null;
  } | null;
  primaryShot?: string | null;
  gallery?: GalleryItem[];
  compare?: CompareItem[];
  layers?: LayerItem[];
};

type NativeSession = {
  jobId: string;
  tool: "OpenROAD" | "KLayout";
  state: string;
  mode: "view" | "edit";
  pid?: number | null;
  reason?: string | null;
};

function withKey(url: string, k: string | number) {
  return `${url}${url.includes("?") ? "&" : "?"}k=${k}`;
}

/**
 * Lab canvas: screenshot of real layout is the default.
 * OpenROAD -web is opt-in — auto-start hid the PNG behind a blank iframe.
 */
export function FlowLabLayoutCanvas({
  phaseId,
  variant,
  refreshKey,
  stageDone,
  runId,
  onCandidateCreated,
  allowCandidate = true,
}: {
  phaseId: LayoutPhaseId;
  variant: string;
  refreshKey: number;
  stageDone: boolean;
  runId?: string | null;
  onCandidateCreated?: (runId: string) => void;
  allowCandidate?: boolean;
}) {
  const [meta, setMeta] = useState<PreviewMeta | null>(null);
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [viewerBusy, setViewerBusy] = useState(false);
  const [viewerErr, setViewerErr] = useState<string | null>(null);
  const [mode, setMode] = useState<"image" | "viewer">("image");
  const [imgErr, setImgErr] = useState(false);
  const [regenBusy, setRegenBusy] = useState(false);
  const [activeShot, setActiveShot] = useState<string | null>(null);
  const [compareId, setCompareId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewportMode>("single");
  const [splitPct, setSplitPct] = useState(50);
  const [layersOpen, setLayersOpen] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [watching, setWatching] = useState(true);
  const [bridgeBusy, setBridgeBusy] = useState(false);
  const [bridgeMessage, setBridgeMessage] = useState<string | null>(null);
  const [nativeSession, setNativeSession] = useState<NativeSession | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [bridgeState, setBridgeState] = useState<"synced" | "updated" | "missing" | "error">("missing");
  const vpRef = useRef<LayoutViewportHandle>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const metaRef = useRef<PreviewMeta | null>(null);
  const metaRequestRef = useRef(0);
  const metaAbortRef = useRef<AbortController | null>(null);
  const eventRefreshTimerRef = useRef<number | undefined>(undefined);

  const nativeSessionActive =
    nativeSession?.state === "QUEUED" || nativeSession?.state === "RUNNING";

  function nativeToolFor(metaValue: PreviewMeta): NativeSession["tool"] {
    const path = `${metaValue.artifact?.path ?? metaValue.odb ?? ""}`.toLowerCase();
    return phaseId === "pkg" || /\.(gds|oas|lyrdb)$/.test(path) ? "KLayout" : "OpenROAD";
  }

  // A native GUI remains alive until the user closes it. Keep the status in
  // the canvas so the user can see the real PID and stop exactly this session;
  // do not poll the whole job history or start any work from this observer.
  useEffect(() => {
    const jobId = nativeSession?.jobId;
    if (!jobId || !nativeSessionActive) return;
    let disposed = false;
    const poll = async () => {
      try {
        const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
          cache: "no-store",
        });
        if (!response.ok || disposed) return;
        const job = (await response.json()) as {
          state?: string;
          pid?: number | null;
          reason?: string | null;
          termination_cause?: string | null;
        };
        if (disposed) return;
        const state = String(job.state || "RUNNING");
        setNativeSession((current) =>
          current?.jobId === jobId
            ? {
                ...current,
                state,
                pid: job.pid ?? current.pid,
                reason: job.reason ?? job.termination_cause ?? current.reason,
              }
            : current,
        );
        if (state !== "QUEUED" && state !== "RUNNING") {
          setBridgeMessage(
            state === "COMPLETED"
              ? "Native session closed; the last saved artifact remains selected."
              : `Native session ${state.toLowerCase()}${job.reason ? ` · ${job.reason}` : ""}`,
          );
        }
      } catch {
        // A transient agent restart must not erase the last known session.
      }
    };
    void poll();
    const interval = window.setInterval(() => void poll(), 1000);
    return () => {
      disposed = true;
      window.clearInterval(interval);
    };
  }, [nativeSession?.jobId, nativeSessionActive]);

  const loadMeta = useCallback(async (resetView = false) => {
    const requestId = metaRequestRef.current + 1;
    metaRequestRef.current = requestId;
    metaAbortRef.current?.abort();
    const controller = new AbortController();
    metaAbortRef.current = controller;
    const runQuery = runId ? `&run_id=${encodeURIComponent(runId)}` : "";
    const authority = runId ? "candidate" : "finish";
    try {
      const [res, artifactsRes] = await Promise.all([
        fetch(
          `/api/layout-preview?phase=${encodeURIComponent(phaseId)}&variant=${encodeURIComponent(variant)}${runQuery}`,
          { cache: "no-store", signal: controller.signal },
        ),
        fetch(
          `/api/artifacts?authority=${authority}&variant=${encodeURIComponent(variant)}&limit=2000${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`,
          { cache: "no-store", signal: controller.signal },
        ),
      ]);
      if (requestId !== metaRequestRef.current) return;
      if (!res.ok) {
        setMeta(null);
        metaRef.current = null;
        setBridgeState("missing");
        setMetadataError(`Layout metadata unavailable (HTTP ${res.status})`);
        return;
      }
      const data = (await res.json()) as PreviewMeta;
      if (requestId !== metaRequestRef.current) return;
      if (data.artifact?.exists && artifactsRes.ok) {
        const artifactData = (await artifactsRes.json()) as {
          artifacts?: Array<{
            artifact_id?: string;
            relative_path?: string;
            content_hash?: string | null;
            authority?: string;
            mutable?: boolean;
            revision?: number;
          }>;
        };
        const expected =
          data.artifact.relativePath ??
          `tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${variant}/` +
            data.artifact.path;
        const ref = artifactData.artifacts?.find(
          (item) => item.relative_path === expected,
        );
        if (ref) {
          data.artifact = {
            ...data.artifact,
            artifactId: ref.artifact_id,
            contentHash: ref.content_hash,
            authority: ref.authority,
            mutable: ref.mutable,
            revision: ref.revision ?? data.artifact.revision,
          };
        }
      }
      if (requestId !== metaRequestRef.current) return;
      const oldRevision = metaRef.current?.artifact?.revision ?? null;
      const changed = data.artifact?.revision !== oldRevision;
      metaRef.current = data;
      setMeta(data);
      setMetadataError(null);
      setBridgeState(data.artifact?.exists ? changed && oldRevision ? "updated" : "synced" : "missing");
      if (resetView || changed) {
        setImgErr(false);
        setMode("image");
        setViewerUrl(null);
        setCompareId(null);
        setViewMode("single");
        setActiveShot(data.primaryShot ?? data.gallery?.[0]?.file ?? null);
        if (changed && oldRevision) {
          setBridgeMessage("Native artifact changed — layout refreshed from the saved database.");
        }
      }
    } catch (e) {
      if (controller.signal.aborted || requestId !== metaRequestRef.current) return;
      setBridgeState("error");
      setMetadataError(e instanceof Error ? e.message : "Layout metadata unavailable");
    }
  }, [phaseId, runId, variant]);

  const startViewer = useCallback(async () => {
    if (!meta?.odb) return;
    setViewerBusy(true);
    setViewerErr(null);
    try {
      const res = await fetch("/api/viewer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "start",
          stage: phaseId === "pdn" ? "floorplan" : phaseId === "pkg" ? "finish" : phaseId,
          variant,
          artifact: meta.odb,
          run_id: runId ?? undefined,
        }),
      });
      const data = await res.json();
      if (data.url) {
        await new Promise((r) => setTimeout(r, 1800));
        setViewerUrl(data.url);
        setMode("viewer");
      } else {
        setViewerErr(data.message || data.error || "Viewer not started — keeping screenshot");
        setMode("image");
      }
    } catch (e) {
      setViewerErr(e instanceof Error ? e.message : "Viewer error");
      setMode("image");
    } finally {
      setViewerBusy(false);
    }
  }, [meta?.odb, phaseId, runId, variant]);

  const regenImage = useCallback(async () => {
    setRegenBusy(true);
    setImgErr(false);
    setMetadataError(null);
    try {
      const res = await fetch("/api/layout-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phase: phaseId, variant, run_id: runId ?? undefined }),
      });
      const body = (await res.json().catch(() => ({}))) as {
        pending?: boolean;
        job_id?: string;
        state?: string;
        message?: string;
      };
      if (!res.ok) {
        throw new Error(body.message || `Preview request failed (HTTP ${res.status})`);
      }
      let finalState = body.state;
      let finalReason = body.message || null;
      if (body.pending && body.job_id) {
        setBridgeMessage("Rendering the current ODB preview in the local agent…");
        const deadline = Date.now() + 600_000;
        while (
          (finalState === "QUEUED" || finalState === "RUNNING" || !finalState) &&
          Date.now() < deadline
        ) {
          await new Promise((resolve) => window.setTimeout(resolve, 500));
          const jobResponse = await fetch(
            `/api/jobs/${encodeURIComponent(body.job_id)}`,
            { cache: "no-store" },
          );
          if (!jobResponse.ok) {
            throw new Error("Local agent preview status unavailable");
          }
          const job = (await jobResponse.json()) as {
            state?: string;
            reason?: string | null;
            report?: { reason?: string | null };
          };
          finalState = job.state;
          finalReason = job.reason || job.report?.reason || finalReason;
        }
        if (finalState === "QUEUED" || finalState === "RUNNING" || !finalState) {
          throw new Error("Live preview timed out while waiting for the local agent");
        }
        if (finalState !== "COMPLETED") {
          throw new Error(finalReason || `Live preview ${finalState.toLowerCase()}`);
        }
      }
      await loadMeta(true);
      setBridgeMessage("Live preview synchronized from the saved ODB.");
    } catch (e) {
      setBridgeState("error");
      setMetadataError(e instanceof Error ? e.message : "Live preview unavailable");
    } finally {
      setRegenBusy(false);
    }
  }, [loadMeta, phaseId, runId, variant]);

  // A phase/profile change invalidates all in-flight metadata requests. This
  // prevents a late response from an earlier checkpoint from repopulating
  // the viewer or enabling controls for the new context with the wrong file.
  useEffect(() => {
    metaRequestRef.current += 1;
    metaAbortRef.current?.abort();
    metaAbortRef.current = null;
    metaRef.current = null;
    setMeta(null);
    setImgErr(false);
    setViewerUrl(null);
    setViewerErr(null);
    setBridgeState("missing");
    setMetadataError(null);
    return () => {
      metaRequestRef.current += 1;
      metaAbortRef.current?.abort();
      metaAbortRef.current = null;
    };
  }, [phaseId, runId, variant]);

  useEffect(() => {
    void loadMeta(true);
  }, [loadMeta, refreshKey]);

  useEffect(() => {
    if (!watching || !meta?.artifact?.exists) return;
    let disposed = false;
    let timer: number | undefined;
    const schedule = () => {
      if (disposed) return;
      timer = window.setTimeout(() => {
        timer = undefined;
        void loadMeta(false);
        schedule();
      }, document.visibilityState === "visible" ? 5000 : 30000);
    };
    const onVisibilityChange = () => {
      if (timer !== undefined) window.clearTimeout(timer);
      timer = undefined;
      schedule();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    schedule();
    return () => {
      disposed = true;
      document.removeEventListener("visibilitychange", onVisibilityChange);
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [loadMeta, meta?.artifact?.exists, watching]);

  useEffect(() => {
    if (!watching) return;
    const onAgentEvent = (event: Event) => {
      const detail = (event as CustomEvent<{ type?: string }>).detail;
      if (
        detail?.type === "artifact.changed" ||
        detail?.type === "artifact.added" ||
        detail?.type === "comparison.invalidated"
      ) {
        if (eventRefreshTimerRef.current !== undefined) return;
        eventRefreshTimerRef.current = window.setTimeout(() => {
          eventRefreshTimerRef.current = undefined;
          void loadMeta(false);
        }, 500);
      }
    };
    window.addEventListener("pdflow:agent-event", onAgentEvent);
    return () => {
      window.removeEventListener("pdflow:agent-event", onAgentEvent);
      if (eventRefreshTimerRef.current !== undefined) {
        window.clearTimeout(eventRefreshTimerRef.current);
        eventRefreshTimerRef.current = undefined;
      }
    };
  }, [loadMeta, watching]);

  useEffect(() => {
    function onFs() {
      setFullscreen(Boolean(document.fullscreenElement));
    }
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const gallery = meta?.gallery ?? [];
  const compareList = meta?.compare ?? [];
  const layers = meta?.layers ?? [];
  const compare = compareList.find((c) => c.id === compareId) ?? null;
  const nativeToolLabel = meta
    ? nativeToolFor(meta)
    : phaseId === "pkg"
      ? "KLayout"
      : "OpenROAD";

  const primaryUrl = (() => {
    const cacheKey = `${refreshKey}:${meta?.artifact?.revision ?? "none"}`;
    if (compare && viewMode !== "single") return withKey(compare.left.url, cacheKey);
    if (activeShot && activeShot !== meta?.primaryShot) {
      const hit = gallery.find((g) => g.file === activeShot);
      if (hit) return withKey(hit.url, cacheKey);
      return withKey(
        `/api/layout-preview/image?shot=${encodeURIComponent(activeShot)}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`,
        cacheKey,
      );
    }
    return meta?.imageUrl ? withKey(meta.imageUrl, cacheKey) : null;
  })();

  const compareUrl =
    compare && viewMode !== "single"
      ? withKey(compare.right.url, `${refreshKey}:${meta?.artifact?.revision ?? "none"}`)
      : null;

  const showViewer = mode === "viewer" && viewerUrl;
  const imageSrc = primaryUrl && !imgErr ? primaryUrl : null;

  function selectShot(file: string) {
    setActiveShot(file);
    setCompareId(null);
    setViewMode("single");
    setMode("image");
    setImgErr(false);
  }

  function selectCompare(id: string) {
    const next = compareId === id ? null : id;
    setCompareId(next);
    setViewMode(next ? "wipe" : "single");
    setMode("image");
    setSplitPct(50);
  }

  function soloLayer(layer: LayerItem) {
    if (layer.soloShot && layer.soloAvailable) {
      selectShot(layer.soloShot);
    }
  }

  async function toggleFullscreen() {
    const el = rootRef.current;
    if (!el) return;
    try {
      if (!document.fullscreenElement) {
        await el.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (e) {
      // Tauri/WebView hosts may not expose the browser fullscreen permission.
      // Keep the failure inside the workbench instead of leaking an unhandled
      // promise rejection into the desktop shell.
      setViewerErr(e instanceof Error ? `Fullscreen unavailable: ${e.message}` : "Fullscreen unavailable in this window");
    }
  }

  async function openNativeTool(mode: "view" | "edit" = "view") {
    const currentMeta = meta;
    const artifact = currentMeta?.artifact?.path ?? currentMeta?.odb;
    if (!artifact || !currentMeta) return;
    setBridgeBusy(true);
    setBridgeMessage(null);
    try {
      let openRunId = runId ?? undefined;
      if (mode === "edit" && !openRunId) {
        if (
          !window.confirm(
            "Create an isolated candidate copy and open it in OpenROAD? The finish remains read-only.",
          )
        ) {
          return;
        }
        const runResponse = await fetch("/api/runs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ surface: "flow", profile: "flowlab-candidate" }),
        });
        if (!runResponse.ok) {
          setBridgeState("error");
          setBridgeMessage("Candidate run could not be created.");
          return;
        }
        const runBody = (await runResponse.json()) as {
          run?: { run_id?: string };
        };
        openRunId = runBody.run?.run_id;
        if (!openRunId) {
          setBridgeState("error");
          setBridgeMessage("Candidate run did not return a run_id.");
          return;
        }
        onCandidateCreated?.(openRunId);
      }
      const endpoint = currentMeta.artifact?.artifactId
        ? "/api/artifacts/" + encodeURIComponent(currentMeta.artifact.artifactId) + "/open"
        : "/api/open";
      const requestBody = currentMeta.artifact?.artifactId
        ? { mode, run_id: openRunId }
        : { artifact, variant, mode, run_id: openRunId };
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      const responseBody = await res.json();
      if (responseBody.launched) {
        const delegated =
          responseBody.job && typeof responseBody.job === "object"
            ? responseBody.job
            : responseBody;
        const jobId = typeof delegated.job_id === "string" ? delegated.job_id : null;
        if (jobId) {
          setNativeSession({
            jobId,
            tool: nativeToolFor(currentMeta),
            state: String(delegated.state || "QUEUED"),
            mode,
            pid: typeof delegated.pid === "number" ? delegated.pid : null,
          });
        }
        setBridgeMessage(responseBody.message || "Native tool started");
        return;
      }
      if (responseBody.command) {
        await navigator.clipboard?.writeText(responseBody.command).catch(() => undefined);
        setBridgeMessage(`${responseBody.message || "Desktop unavailable"} Command copied.`);
        return;
      }
      setBridgeState("error");
      setBridgeMessage(responseBody.message || responseBody.error || "Native tool could not be started");
    } catch (e) {
      setBridgeState("error");
      setBridgeMessage(e instanceof Error ? e.message : "Native tool could not be started");
    } finally {
      setBridgeBusy(false);
    }
  }

  async function stopNativeSession() {
    const session = nativeSession;
    if (!session || !nativeSessionActive) return;
    setBridgeBusy(true);
    setBridgeMessage("Stopping the selected native session…");
    try {
      const response = await fetch(
        `/api/jobs/${encodeURIComponent(session.jobId)}/cancel`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        },
      );
      const body = (await response.json().catch(() => ({}))) as {
        state?: string;
        reason?: string | null;
      };
      if (!response.ok) {
        throw new Error(body.reason || `Stop request failed (HTTP ${response.status})`);
      }
      setNativeSession((current) =>
        current?.jobId === session.jobId
          ? { ...current, state: body.state || current.state, reason: body.reason ?? current.reason }
          : current,
      );
    } catch (e) {
      setBridgeState("error");
      setBridgeMessage(e instanceof Error ? e.message : "Native session could not be stopped");
    } finally {
      setBridgeBusy(false);
    }
  }

  return (
    <div className="fl-layout-canvas" ref={rootRef}>
      <div className="fl-layout-toolbar">
        <div className="fl-layout-title">
          <strong>{meta?.label ?? "Layout"}</strong>
          {meta?.layerHint && <span className="fl-layout-hint">{meta.layerHint}</span>}
          {meta?.image?.source && (
            <span className="fl-layout-src">{meta.image.source.replace("_", " ")}</span>
          )}
        </div>
        <div className="fl-layout-actions">
          {compareList.map((c) => (
            <button
              key={c.id}
              type="button"
              className={clsx("btn-ghost btn-sm", compareId === c.id && "chip-active")}
              onClick={() => selectCompare(c.id)}
            >
              {c.label}
            </button>
          ))}
          {compare && (
            <>
              <button
                type="button"
                className={clsx("btn-ghost btn-sm", viewMode === "wipe" && "chip-active")}
                onClick={() => setViewMode("wipe")}
                title="Wipe"
              >
                <SquareSplitHorizontal size={14} aria-hidden />
                Wipe
              </button>
              <button
                type="button"
                className={clsx("btn-ghost btn-sm", viewMode === "split" && "chip-active")}
                onClick={() => setViewMode("split")}
                title="Split"
              >
                <Columns2 size={14} aria-hidden />
                Split
              </button>
            </>
          )}
          <button
            type="button"
            className="btn-ghost btn-sm"
            disabled={!imageSrc}
            onClick={() => vpRef.current?.zoomBy(1.22)}
            title="Zoom +"
          >
            <ZoomIn size={14} aria-hidden />
          </button>
          <button
            type="button"
            className="btn-ghost btn-sm"
            disabled={!imageSrc}
            onClick={() => vpRef.current?.zoomBy(0.82)}
            title="Zoom −"
          >
            <ZoomOut size={14} aria-hidden />
          </button>
          <button
            type="button"
            className="btn-ghost btn-sm"
            disabled={!imageSrc}
            onClick={() => vpRef.current?.fit()}
            title="Fit (0)"
          >
            Fit
          </button>
          <button
            type="button"
            className="btn-ghost btn-sm"
            disabled={!imageSrc}
            onClick={() => void toggleFullscreen()}
            title="Fullscreen (F)"
          >
            {fullscreen ? <Minimize2 size={14} aria-hidden /> : <Maximize2 size={14} aria-hidden />}
            {fullscreen ? "Esci" : "Full"}
          </button>
          <button
            type="button"
            className={clsx("btn-ghost btn-sm", mode === "image" && "chip-active")}
            disabled={!imageSrc}
            onClick={() => setMode("image")}
          >
            Layout
          </button>
          {meta?.odbExists && (
            <button
              type="button"
              className={clsx("btn-ghost btn-sm", mode === "viewer" && "chip-active")}
              disabled={viewerBusy}
              onClick={() => void startViewer()}
            >
              {viewerBusy ? "Starting viewer…" : "Web Viewer"}
            </button>
          )}
          {meta?.odbExists && (
            <button
              type="button"
              className="btn-ghost btn-sm"
              disabled={regenBusy}
              onClick={() => void regenImage()}
            >
              {regenBusy ? "Rendering…" : "PNG from ODB"}
            </button>
          )}
        </div>
      </div>

      {meta?.artifact && (
        <section className="fl-layout-bridge" aria-label="Native tool bridge">
          <div className="fl-layout-bridge-copy">
            <div className="fl-layout-bridge-title">
              <Monitor size={15} aria-hidden />
              <strong>{phaseId === "floorplan" ? "Floorplan tool bridge" : "Native tool bridge"}</strong>
              <span className={clsx("pill", bridgeState === "synced" && "ok", bridgeState === "updated" && "warn", bridgeState === "error" && "bad")}>
                {bridgeState === "synced" ? "ODB linked" : bridgeState === "updated" ? "Updated" : bridgeState === "missing" ? "Waiting for ODB" : "Sync error"}
              </span>
            </div>
            <code>{meta.artifact.path}</code>
            <span className="fl-layout-bridge-meta">
              {meta.artifact.exists
                ? `${Math.round(meta.artifact.bytes / 1024)} KB · saved ${meta.artifact.modifiedAt ?? "—"}`
                : "Run the phase to create the live database"}
            </span>
            {meta.artifact.exists && (
              <span className="fl-layout-bridge-meta">
                {meta.artifact.authority === "candidate"
                  ? "CANDIDATE · EDITABLE"
                  : "FINISH · READ ONLY"} · rev {meta.artifact.revision ?? "—"}
                {meta.artifact.contentHash
                  ? ` · sha256 ${meta.artifact.contentHash.slice(0, 12)}…`
                  : " · hash unavailable"}
              </span>
            )}
          </div>
          <div className="fl-layout-bridge-actions">
            <button
              type="button"
              className="btn-primary btn-sm"
              disabled={!meta.artifact.exists || bridgeBusy}
              onClick={() => void openNativeTool()}
            >
              {bridgeBusy ? "Opening…" : `Open in ${nativeToolLabel}`}
            </button>
            <button
              type="button"
              className="btn-ghost btn-sm"
              disabled={!meta.artifact.exists || bridgeBusy || !allowCandidate}
              onClick={() => void openNativeTool("edit")}
              title={allowCandidate ? "Open a candidate copy; the finish is never written" : "Lab ASAP7 finish is read-only; select a new experiment profile instead"}
            >
              {allowCandidate ? "Edit candidate" : "Read-only finish"}
            </button>
            <button
              type="button"
              className="btn-ghost btn-sm"
              disabled={bridgeBusy}
              onClick={() => void loadMeta(false)}
            >
              <RefreshCw size={13} aria-hidden /> Refresh
            </button>
            <label className="fl-layout-watch">
              <input
                type="checkbox"
                checked={watching}
                onChange={(e) => setWatching(e.target.checked)}
              />
              Auto-sync
            </label>
          </div>
          {(metadataError || bridgeMessage) && (
            <p className="fl-layout-bridge-message">{metadataError || bridgeMessage}</p>
          )}
          {nativeSession && (
            <div className="fl-layout-native-session" role="status" aria-live="polite">
              <span className="fl-layout-native-session-label">
                {nativeSession.tool} · {nativeSession.state}
              </span>
              {nativeSession.pid != null && <code>PID {nativeSession.pid}</code>}
              <code>job {nativeSession.jobId.slice(-12)}</code>
              {nativeSessionActive ? (
                <button
                  type="button"
                  className="btn-danger btn-sm"
                  disabled={bridgeBusy}
                  onClick={() => void stopNativeSession()}
                >
                  {bridgeBusy ? "Stopping…" : "Stop session"}
                </button>
              ) : (
                <span className="fl-layout-native-session-reason">
                  {nativeSession.reason || "session closed"}
                </span>
              )}
            </div>
          )}
        </section>
      )}

      <div className={clsx("fl-layout-stage", !stageDone && "pending")}>
        {showViewer ? (
          <iframe
            title={`OpenROAD layout ${phaseId}`}
            src={viewerUrl}
            className="fl-layout-iframe"
            allow="fullscreen"
          />
        ) : imageSrc ? (
          <>
            <LayoutViewport
              ref={vpRef}
              src={imageSrc}
              alt={meta?.label ?? "Layout preview"}
              compareSrc={compareUrl}
              leftLabel={compare?.left.title}
              rightLabel={compare?.right.title}
              mode={compare ? viewMode : "single"}
              splitPct={splitPct}
              onSplitChange={setSplitPct}
              resetKey={`${phaseId}:${activeShot ?? ""}:${compareId ?? ""}:${viewMode}`}
            />
            {layers.length > 0 && layersOpen && (
              <aside className="fl-layer-hud" aria-label="Layer legend">
                <header>
                  <Layers size={13} aria-hidden />
                  Display Control
                  <button
                    type="button"
                    className="fl-layer-close"
                    onClick={() => setLayersOpen(false)}
                    aria-label="Hide layer"
                  >
                    ×
                  </button>
                </header>
                <ul>
                  {layers.map((layer) => (
                    <li key={layer.id}>
                      <button
                        type="button"
                        className={clsx(
                          "fl-layer-row",
                          layer.soloShot && activeShot === layer.soloShot && "is-solo",
                        )}
                        onClick={() => soloLayer(layer)}
                        title={
                          layer.soloAvailable
                            ? `Show ${layer.name}`
                            : "Legend (static screenshot — Web Viewer to toggle layers)"
                        }
                      >
                        <i style={{ background: layer.color }} />
                        <span className="fl-layer-name">{layer.name}</span>
                        {layer.soloAvailable ? (
                          <span className="fl-layer-solo">solo</span>
                        ) : (
                          <span className="fl-layer-legend">legend</span>
                        )}
                      </button>
                      <p>{layer.role}</p>
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  className="btn-ghost btn-sm fl-layer-reset"
                  disabled={!activeShot || activeShot === meta?.primaryShot}
                  onClick={() => selectShot(meta?.primaryShot ?? gallery[0]?.file ?? "")}
                >
                  All layers
                </button>
              </aside>
            )}
            {!layersOpen && layers.length > 0 && (
              <button
                type="button"
                className="fl-layer-reopen"
                onClick={() => setLayersOpen(true)}
              >
                <Layers size={14} aria-hidden />
                Layer
              </button>
            )}
            {gallery.length > 1 && (
              <div className="fl-filmstrip" role="list" aria-label="Related screenshots">
                {gallery.map((shot) => (
                  <button
                    key={shot.file}
                    type="button"
                    role="listitem"
                    className={clsx(
                      "fl-film-thumb",
                      activeShot === shot.file && viewMode === "single" && !compareId && "is-active",
                    )}
                    onClick={() => selectShot(shot.file)}
                    title={shot.caption}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={withKey(shot.url, refreshKey)} alt="" />
                    <span>{shot.title}</span>
                  </button>
                ))}
              </div>
            )}
            {activeShot && activeShot !== meta?.primaryShot && viewMode === "single" && (
              <p className="fl-shot-banner">
                Screenshot in-app · {gallery.find((g) => g.file === activeShot)?.title ?? activeShot}
              </p>
            )}
          </>
        ) : (
          <div className="fl-layout-empty">
            {phaseId === "synth" ? (
              <>
                <p>
                  Synthesis produces the <strong>netlist</strong>, not a layout in the die
                  (area 0×0). Cells appear at <strong>floorplan / place</strong>.
                </p>
                <p className="fl-layout-empty-hint">
                  Run floorplan, then place and route to see PDN, cells, and metal.
                </p>
              </>
            ) : (
              <>
                <p>
                  {stageDone || meta?.odbExists
                    ? "Screenshot missing for this phase."
                    : "Run the ORFS phase to see real placement, PDN, and routing."}
                </p>
                {meta?.odb && <code>{meta.odb}</code>}
              </>
            )}
          </div>
        )}
      </div>

      {(viewerErr || imgErr) && (
        <p className="fl-layout-warn" role="status">
          {viewerErr}
          {imgErr ? " Screenshot not loaded." : ""}
        </p>
      )}

      {meta?.odb && (
        <p className="fl-layout-meta">
          ODB: <code>{meta.odb}</code>
          {meta.odbExists ? " · present" : " · missing"}
          {showViewer && (
            <>
              {" · "}
              <a href={viewerUrl!} target="_blank" rel="noreferrer">
                open viewer in tab
              </a>
            </>
          )}
        </p>
      )}
    </div>
  );
}

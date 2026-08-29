"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import {
  Columns2,
  Layers,
  Maximize2,
  Minimize2,
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
  primaryShot?: string | null;
  gallery?: GalleryItem[];
  compare?: CompareItem[];
  layers?: LayerItem[];
};

function withKey(url: string, k: number) {
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
}: {
  phaseId: LayoutPhaseId;
  variant: string;
  refreshKey: number;
  stageDone: boolean;
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
  const vpRef = useRef<LayoutViewportHandle>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const loadMeta = useCallback(async () => {
    setImgErr(false);
    setMode("image");
    setViewerUrl(null);
    setCompareId(null);
    setViewMode("single");
    setActiveShot(null);
    const res = await fetch(
      `/api/layout-preview?phase=${encodeURIComponent(phaseId)}&variant=${encodeURIComponent(variant)}`,
    );
    if (!res.ok) {
      setMeta(null);
      return;
    }
    const data = (await res.json()) as PreviewMeta;
    setMeta(data);
    setActiveShot(data.primaryShot ?? data.gallery?.[0]?.file ?? null);
  }, [phaseId, variant]);

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
        }),
      });
      const data = await res.json();
      if (data.url) {
        await new Promise((r) => setTimeout(r, 1800));
        setViewerUrl(data.url);
        setMode("viewer");
      } else {
        setViewerErr(data.message || data.error || "Viewer non avviato — resta lo screenshot");
        setMode("image");
      }
    } catch (e) {
      setViewerErr(e instanceof Error ? e.message : "Errore viewer");
      setMode("image");
    } finally {
      setViewerBusy(false);
    }
  }, [meta?.odb, phaseId, variant]);

  const regenImage = useCallback(async () => {
    setRegenBusy(true);
    setImgErr(false);
    try {
      const res = await fetch("/api/layout-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phase: phaseId, variant }),
      });
      if (res.ok) {
        await loadMeta();
      }
    } finally {
      setRegenBusy(false);
    }
  }, [loadMeta, phaseId, variant]);

  useEffect(() => {
    void loadMeta();
  }, [loadMeta, refreshKey]);

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

  const primaryUrl = (() => {
    if (compare && viewMode !== "single") return withKey(compare.left.url, refreshKey);
    if (activeShot && activeShot !== meta?.primaryShot) {
      const hit = gallery.find((g) => g.file === activeShot);
      if (hit) return withKey(hit.url, refreshKey);
      return withKey(
        `/api/layout-preview/image?shot=${encodeURIComponent(activeShot)}`,
        refreshKey,
      );
    }
    return meta?.imageUrl ? withKey(meta.imageUrl, refreshKey) : null;
  })();

  const compareUrl =
    compare && viewMode !== "single" ? withKey(compare.right.url, refreshKey) : null;

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
    if (!document.fullscreenElement) {
      await el.requestFullscreen();
    } else {
      await document.exitFullscreen();
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
              {viewerBusy ? "Avvio viewer…" : "Web Viewer"}
            </button>
          )}
          {meta?.odbExists && (
            <button
              type="button"
              className="btn-ghost btn-sm"
              disabled={regenBusy}
              onClick={() => void regenImage()}
            >
              {regenBusy ? "Genero…" : "PNG da ODB"}
            </button>
          )}
        </div>
      </div>

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
                    aria-label="Nascondi layer"
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
                            ? `Mostra ${layer.name}`
                            : "Legenda (screenshot statico — Web Viewer per togglare i layer)"
                        }
                      >
                        <i style={{ background: layer.color }} />
                        <span className="fl-layer-name">{layer.name}</span>
                        {layer.soloAvailable ? (
                          <span className="fl-layer-solo">solo</span>
                        ) : (
                          <span className="fl-layer-legend">legenda</span>
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
                  Tutti i layer
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
              <div className="fl-filmstrip" role="list" aria-label="Screenshot correlati">
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
                  La sintesi produce il <strong>netlist</strong>, non un layout nel die
                  (area 0×0). Le celle compaiono al <strong>floorplan / place</strong>.
                </p>
                <p className="fl-layout-empty-hint">
                  Esegui floorplan, poi place e route per vedere PDN, celle e metal.
                </p>
              </>
            ) : (
              <>
                <p>
                  {stageDone || meta?.odbExists
                    ? "Screenshot assente per questa fase."
                    : "Esegui la fase ORFS per vedere placement, PDN e routing reali."}
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
          {imgErr ? " Screenshot non caricato." : ""}
        </p>
      )}

      {meta?.odb && (
        <p className="fl-layout-meta">
          ODB: <code>{meta.odb}</code>
          {meta.odbExists ? " · presente" : " · mancante"}
          {showViewer && (
            <>
              {" · "}
              <a href={viewerUrl!} target="_blank" rel="noreferrer">
                apri viewer in tab
              </a>
            </>
          )}
        </p>
      )}
    </div>
  );
}

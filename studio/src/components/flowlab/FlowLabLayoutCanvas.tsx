"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";

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

type PreviewMeta = {
  label: string;
  layerHint?: string;
  odbExists: boolean;
  odb: string | null;
  imageUrl: string | null;
  image?: { source: string; rel: string } | null;
  physical: boolean;
};

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
  const [mode, setMode] = useState<"viewer" | "image">("image");
  const [imgErr, setImgErr] = useState(false);
  const [regenBusy, setRegenBusy] = useState(false);

  const loadMeta = useCallback(async () => {
    setImgErr(false);
    const res = await fetch(
      `/api/layout-preview?phase=${encodeURIComponent(phaseId)}&variant=${encodeURIComponent(variant)}`,
    );
    if (!res.ok) {
      setMeta(null);
      return;
    }
    setMeta(await res.json());
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
        setViewerUrl(data.url);
        setMode("viewer");
      } else {
        setViewerErr(data.message || data.error || "Viewer non avviato");
      }
    } catch (e) {
      setViewerErr(e instanceof Error ? e.message : "Errore viewer");
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
        setMode("image");
      }
    } finally {
      setRegenBusy(false);
    }
  }, [loadMeta, phaseId, variant]);

  useEffect(() => {
    void loadMeta();
  }, [loadMeta, refreshKey]);

  useEffect(() => {
    setViewerUrl(null);
    setViewerErr(null);
    if (meta?.odbExists && meta.physical) {
      void startViewer();
    }
  }, [meta?.odbExists, meta?.physical, phaseId, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const imageSrc =
    meta?.imageUrl && !imgErr
      ? `${meta.imageUrl}${meta.imageUrl.includes("?") ? "&" : "?"}k=${refreshKey}`
      : null;

  return (
    <div className="fl-layout-canvas">
      <div className="fl-layout-toolbar">
        <div className="fl-layout-title">
          <strong>{meta?.label ?? "Layout"}</strong>
          {meta?.layerHint && <span className="fl-layout-hint">{meta.layerHint}</span>}
          {meta?.image?.source && (
            <span className="fl-layout-src">{meta.image.source.replace("_", " ")}</span>
          )}
        </div>
        <div className="fl-layout-actions">
          {meta?.odbExists && (
            <>
              <button
                type="button"
                className={clsx("btn-ghost btn-sm", mode === "viewer" && "chip-active")}
                disabled={viewerBusy}
                onClick={() => void startViewer()}
              >
                {viewerBusy ? "Viewer…" : "Web Viewer"}
              </button>
              <button
                type="button"
                className={clsx("btn-ghost btn-sm", mode === "image" && "chip-active")}
                disabled={!imageSrc}
                onClick={() => setMode("image")}
              >
                Screenshot
              </button>
            </>
          )}
          {meta?.odbExists && (
            <button
              type="button"
              className="btn-ghost btn-sm"
              disabled={regenBusy}
              onClick={() => void regenImage()}
            >
              {regenBusy ? "Genero…" : "Rigenera PNG"}
            </button>
          )}
        </div>
      </div>

      <div className={clsx("fl-layout-stage", !stageDone && "pending")}>
        {mode === "viewer" && viewerUrl ? (
          <iframe
            title={`OpenROAD layout ${phaseId}`}
            src={viewerUrl}
            className="fl-layout-iframe"
            allow="fullscreen"
          />
        ) : imageSrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageSrc}
            alt={meta?.label ?? "Layout preview"}
            className="fl-layout-img"
            onError={() => setImgErr(true)}
          />
        ) : (
          <div className="fl-layout-empty">
            <p>
              {stageDone || meta?.odbExists
                ? "Preview in caricamento…"
                : "Esegui la fase ORFS per vedere placement, PDN e routing reali."}
            </p>
            {meta?.odb && <code>{meta.odb}</code>}
          </div>
        )}
      </div>

      {(viewerErr || imgErr) && (
        <p className="fl-layout-warn" role="status">
          {viewerErr}
          {viewerErr && imgErr ? " · " : ""}
          {imgErr ? "Screenshot non disponibile — usa Web Viewer o rigenera PNG." : ""}
        </p>
      )}

      {meta?.odb && (
        <p className="fl-layout-meta">
          ODB: <code>{meta.odb}</code>
          {meta.odbExists ? " · presente" : " · mancante"}
          {" · "}
          Pan/zoom nel Web Viewer · layer M2/M3/M4 in toolbar OpenROAD
        </p>
      )}
    </div>
  );
}

"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import clsx from "clsx";

export type ViewportMode = "single" | "wipe" | "split";

export type LayoutViewportHandle = {
  fit: () => void;
  zoomBy: (factor: number) => void;
};

type Props = {
  src: string;
  alt: string;
  compareSrc?: string | null;
  leftLabel?: string;
  rightLabel?: string;
  mode: ViewportMode;
  splitPct: number;
  onSplitChange: (pct: number) => void;
  resetKey: string;
};

const MIN_SCALE = 0.15;
const MAX_SCALE = 28;

export const LayoutViewport = forwardRef<LayoutViewportHandle, Props>(
  function LayoutViewport(
    {
      src,
      alt,
      compareSrc,
      leftLabel,
      rightLabel,
      mode,
      splitPct,
      onSplitChange,
      resetKey,
    },
    ref,
  ) {
    const wrapRef = useRef<HTMLDivElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);
    const transform = useRef({ scale: 1, tx: 0, ty: 0 });
    const [tick, setTick] = useState(0);
    const [nw, setNw] = useState(800);
    const [nh, setNh] = useState(600);
    const [ready, setReady] = useState(false);
    const drag = useRef<{
      kind: "pan" | "wipe";
      x: number;
      y: number;
      tx: number;
      ty: number;
    } | null>(null);

    const apply = useCallback((scale: number, tx: number, ty: number) => {
      transform.current = { scale, tx, ty };
      setTick((n) => n + 1);
    }, []);

    const fit = useCallback(() => {
      const wrap = wrapRef.current;
      const img = imgRef.current;
      if (!wrap || !img || !img.naturalWidth) return;
      const w = wrap.clientWidth;
      const h = wrap.clientHeight;
      const s = Math.min(w / img.naturalWidth, h / img.naturalHeight) * 0.98;
      const next = Number.isFinite(s) && s > 0 ? s : 1;
      apply(next, (w - img.naturalWidth * next) / 2, (h - img.naturalHeight * next) / 2);
    }, [apply]);

    const zoomAt = useCallback(
      (clientX: number, clientY: number, factor: number) => {
        const wrap = wrapRef.current;
        if (!wrap) return;
        const { scale, tx, ty } = transform.current;
        const rect = wrap.getBoundingClientRect();
        const cx = clientX - rect.left;
        const cy = clientY - rect.top;
        const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
        const x = (cx - tx) / scale;
        const y = (cy - ty) / scale;
        apply(next, cx - x * next, cy - y * next);
      },
      [apply],
    );

    const zoomBy = useCallback(
      (factor: number) => {
        const wrap = wrapRef.current;
        if (!wrap) return;
        const r = wrap.getBoundingClientRect();
        zoomAt(r.left + r.width / 2, r.top + r.height / 2, factor);
      },
      [zoomAt],
    );

    useImperativeHandle(ref, () => ({ fit, zoomBy }), [fit, zoomBy]);

    const onImgLoad = useCallback(() => {
      const img = imgRef.current;
      if (!img) return;
      setNw(img.naturalWidth);
      setNh(img.naturalHeight);
      setReady(true);
      requestAnimationFrame(fit);
    }, [fit]);

    useEffect(() => {
      setReady(false);
    }, [src, resetKey, mode]);

    useEffect(() => {
      const wrap = wrapRef.current;
      if (!wrap) return;
      const ro = new ResizeObserver(() => {
        if (transform.current.scale <= 1.05) fit();
      });
      ro.observe(wrap);
      return () => ro.disconnect();
    }, [fit, ready]);

    useEffect(() => {
      const el = wrapRef.current;
      if (!el) return;
      const onWheel = (e: WheelEvent) => {
        e.preventDefault();
        zoomAt(e.clientX, e.clientY, e.deltaY > 0 ? 0.88 : 1.14);
      };
      el.addEventListener("wheel", onWheel, { passive: false });
      return () => el.removeEventListener("wheel", onWheel);
    }, [zoomAt]);

    useEffect(() => {
      const el = wrapRef.current;
      if (!el) return;
      const onKey = (e: KeyboardEvent) => {
        if (document.activeElement !== el && !el.contains(document.activeElement)) {
          return;
        }
        if (e.key === "+" || e.key === "=") {
          e.preventDefault();
          zoomBy(1.22);
        } else if (e.key === "-" || e.key === "_") {
          e.preventDefault();
          zoomBy(0.82);
        } else if (e.key === "0" || e.key === "f") {
          e.preventDefault();
          fit();
        } else if (e.key === "F") {
          e.preventDefault();
          const root = el.closest(".fl-layout-canvas");
          if (!document.fullscreenElement) {
            void (root ?? el).requestFullscreen();
          } else {
            void document.exitFullscreen();
          }
        }
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, [fit, zoomBy]);

    const onPointerDown = (e: ReactPointerEvent) => {
      if (e.button !== 0 && e.button !== 1) return;
      const target = e.target as HTMLElement;
      if (target.closest("[data-wipe-handle]")) {
        drag.current = {
          kind: "wipe",
          x: e.clientX,
          y: e.clientY,
          tx: transform.current.tx,
          ty: transform.current.ty,
        };
      } else {
        drag.current = {
          kind: "pan",
          x: e.clientX,
          y: e.clientY,
          tx: transform.current.tx,
          ty: transform.current.ty,
        };
      }
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      elFocus();
    };

    const elFocus = () => wrapRef.current?.focus({ preventScroll: true });

    const onPointerMove = (e: ReactPointerEvent) => {
      const wrap = wrapRef.current;
      if (!drag.current || !wrap) return;
      const { scale, tx } = transform.current;
      if (drag.current.kind === "wipe") {
        const rect = wrap.getBoundingClientRect();
        const imgLeft = tx;
        const imgW = nw * scale;
        const local = e.clientX - rect.left - imgLeft;
        onSplitChange(Math.min(92, Math.max(8, (local / imgW) * 100)));
        return;
      }
      apply(
        scale,
        drag.current.tx + (e.clientX - drag.current.x),
        drag.current.ty + (e.clientY - drag.current.y),
      );
    };

    const onPointerUp = () => {
      drag.current = null;
    };

    const { scale, tx, ty } = transform.current;
    const handleLeft = tx + (splitPct / 100) * nw * scale;
    void tick;

    return (
      <div
        ref={wrapRef}
        className={clsx("fl-vp", !ready && "is-loading")}
        tabIndex={0}
        role="application"
        aria-label="Layout viewport: wheel zoom, drag to pan, + − 0 F"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={(e) => zoomAt(e.clientX, e.clientY, 1.7)}
      >
        <div
          className="fl-vp-world"
          style={{
            transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
            transformOrigin: "0 0",
          }}
        >
          {mode === "split" && compareSrc ? (
            <div className="fl-vp-split" style={{ width: nw * 2 + 8, height: nh }}>
              <div className="fl-vp-split-pane" style={{ width: nw, height: nh }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  ref={imgRef}
                  src={src}
                  alt={leftLabel ?? alt}
                  width={nw}
                  height={nh}
                  draggable={false}
                  key={src}
                  onLoad={onImgLoad}
                  onError={() => setReady(true)}
                />
              </div>
              <div className="fl-vp-split-pane" style={{ width: nw, height: nh }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={compareSrc}
                  alt={rightLabel ?? "Compare"}
                  width={nw}
                  height={nh}
                  draggable={false}
                />
              </div>
            </div>
          ) : mode === "wipe" && compareSrc ? (
            <div className="fl-vp-wipe" style={{ width: nw, height: nh }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={compareSrc} alt={rightLabel ?? "After"} width={nw} height={nh} draggable={false} />
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                ref={imgRef}
                src={src}
                alt={leftLabel ?? alt}
                width={nw}
                height={nh}
                draggable={false}
                style={{ clipPath: `inset(0 ${100 - splitPct}% 0 0)` }}
                key={src}
                onLoad={onImgLoad}
                onError={() => setReady(true)}
              />
            </div>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              ref={imgRef}
              src={src}
              alt={alt}
              width={nw}
              height={nh}
              draggable={false}
              key={src}
              onLoad={onImgLoad}
              onError={() => setReady(true)}
            />
          )}
        </div>

        {mode === "wipe" && compareSrc && ready && (
          <button
            type="button"
            data-wipe-handle
            className="fl-vp-wipe-handle"
            style={{ left: handleLeft }}
            aria-label="Drag to compare"
          >
            <span />
          </button>
        )}

        {mode !== "single" && (
          <div className="fl-vp-compare-tags" aria-hidden>
            <span>{leftLabel ?? "A"}</span>
            <span>{rightLabel ?? "B"}</span>
          </div>
        )}

        <div className="fl-vp-hud">
          <span>{Math.round(scale * 100)}%</span>
          <span className="fl-vp-keys">
            wheel · drag · <kbd>+</kbd>
            <kbd>-</kbd>
            <kbd>0</kbd>
            <kbd>F</kbd>
          </span>
        </div>
      </div>
    );
  },
);

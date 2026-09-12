"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, TerminalSquare } from "lucide-react";
import clsx from "clsx";
import { AgentTimeline } from "@/components/AgentTimeline";
import { CommandPalette } from "@/components/CommandPalette";
import { RuntimeStatusBar } from "@/components/RuntimeStatusBar";
import { SiteNav } from "@/components/SiteNav";

type SurfaceKey = "overview" | "flow" | "product" | "package" | "lab" | "tools" | "reference";

type LayoutPreferences = {
  version: 1;
  navigationCollapsed: boolean;
  inspectorOpen: boolean;
  dockOpen: boolean;
  inspectorWidth: number;
  dockHeight: number;
};

const LAYOUT_STORAGE_KEY = "pdflow:workspace-layout:v1";
const DEFAULT_PREFERENCES: LayoutPreferences = {
  version: 1,
  navigationCollapsed: false,
  inspectorOpen: false,
  dockOpen: false,
  inspectorWidth: 320,
  dockHeight: 220,
};

function clampInspectorWidth(value: number): number {
  return Math.min(420, Math.max(280, Math.round(value)));
}

function clampDockHeight(value: number): number {
  return Math.min(900, Math.max(160, Math.round(value)));
}

function getDockMaximum(height: number, immersiveSurface: boolean): number {
  // Keep enough vertical room for the primary workbench. The previous fixed
  // 600px reservation made the runtime dock impossible to open on a normal
  // 720px desktop viewport, which also made the layout feel broken rather
  // than merely compact.
  // Immersive surfaces have a fixed status/context/header band before the
  // canvas. Reserve that band plus the 320px minimum design viewport. This
  // makes the effective dock height shrink on a 720px desktop instead of
  // reducing the viewer to an unusable strip.
  const reservedForWorkbench = immersiveSurface ? 550 : 360;
  return Math.max(
    0,
    Math.min(
      900,
      Math.floor(height * 0.35),
      Math.max(0, height - reservedForWorkbench),
    ),
  );
}

function getRouteInfo(pathname: string): { surface: SurfaceKey; label: string; title: string } {
  if (pathname.startsWith("/product")) return { surface: "product", label: "Product", title: "Product signoff" };
  if (pathname.startsWith("/pkg")) return { surface: "package", label: "Package", title: "Package and system PDN" };
  if (pathname.startsWith("/lab")) return { surface: "lab", label: "Lab", title: "Lab experiments" };
  if (pathname.startsWith("/tools")) return { surface: "tools", label: "Tools", title: "Tool registry and jobs" };
  if (pathname.startsWith("/lessons")) return { surface: "reference", label: "Lessons", title: "Guided lessons" };
  if (pathname.startsWith("/materials")) return { surface: "reference", label: "Materials", title: "Engineering materials" };
  if (pathname.startsWith("/flow")) return { surface: "flow", label: "FlowLab", title: "RTL to physical design" };
  return { surface: "overview", label: "Overview", title: "Current workspace" };
}

function readPreferences(): LayoutPreferences {
  if (typeof window === "undefined") {
    return { ...DEFAULT_PREFERENCES };
  }
  try {
    const raw = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) throw new Error("no saved layout");
    const value = JSON.parse(raw) as Partial<LayoutPreferences>;
    return {
      version: 1,
      navigationCollapsed: value.navigationCollapsed === true,
      inspectorOpen: value.inspectorOpen === true,
      dockOpen: value.dockOpen === true,
      inspectorWidth:
        typeof value.inspectorWidth === "number" && Number.isFinite(value.inspectorWidth)
          ? clampInspectorWidth(value.inspectorWidth)
          : DEFAULT_PREFERENCES.inspectorWidth,
      dockHeight:
        typeof value.dockHeight === "number" && Number.isFinite(value.dockHeight)
          ? clampDockHeight(value.dockHeight)
          : DEFAULT_PREFERENCES.dockHeight,
    };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

function ContextInspector({
  label,
  title,
  pathname,
  onClose,
  onReset,
}: {
  label: string;
  title: string;
  pathname: string;
  onClose: () => void;
  onReset: () => void;
}) {
  return (
    <aside className="workspace-inspector" aria-label={`${label} context inspector`}>
      <div className="workspace-panel-heading">
        <div>
          <span className="workspace-panel-kicker">Context</span>
          <h2>{title}</h2>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close inspector" title="Close inspector">
          <PanelRightClose size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="workspace-inspector-body">
        <div className="context-card">
          <span>Surface</span>
          <strong>{label}</strong>
          <code>{pathname}</code>
        </div>
        <div className="context-card">
          <span>Workspace contract</span>
          <strong>Local native tools</strong>
          <p>Tool sessions, reports and artifacts remain owned by the PDflow local agent.</p>
        </div>
        <div className="context-card context-card-warning">
          <span>Safety</span>
          <strong>Finish is protected</strong>
          <p>Mutating operations use an isolated candidate. Layout changes are not inferred until the tool saves an artifact.</p>
        </div>
        <button type="button" className="btn-ghost" onClick={onReset}>Reset workspace layout</button>
      </div>
    </aside>
  );
}

function WorkspaceDock({ onClose }: { onClose: () => void }) {
  return (
    <section className="workspace-dock" aria-label="Runtime job dock">
      <div className="workspace-dock-heading">
        <div className="workspace-dock-title">
          <TerminalSquare size={16} aria-hidden="true" />
          <strong>Runtime activity</strong>
          <span>jobs, resource limits and provenance</span>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close runtime dock" title="Close runtime dock">
          <PanelRightClose size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="workspace-dock-content">
        <AgentTimeline compact />
      </div>
    </section>
  );
}

function WorkspaceDockRail({ onOpen }: { onOpen: () => void }) {
  const [runningJobs, setRunningJobs] = useState<number | null>(null);

  useEffect(() => {
    let disposed = false;
    const update = (value: unknown) => {
      if (!value || typeof value !== "object") return;
      const count = (value as { running_jobs?: unknown }).running_jobs;
      if (typeof count === "number" && Number.isFinite(count) && !disposed) {
        setRunningJobs(Math.max(0, Math.round(count)));
      }
    };
    const onHealth = (event: Event) =>
      update((event as CustomEvent<unknown>).detail);
    window.addEventListener("pdflow:runtime-health", onHealth);
    void fetch("/api/agent/health", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then(update)
      .catch(() => undefined);
    return () => {
      disposed = true;
      window.removeEventListener("pdflow:runtime-health", onHealth);
    };
  }, []);

  return (
    <div className="workspace-dock-rail" aria-label="Runtime dock collapsed">
      <div className="workspace-dock-rail-copy">
        <TerminalSquare size={13} aria-hidden="true" />
        <span>Runtime</span>
        <small>
          {runningJobs == null
            ? "status loading"
            : runningJobs > 0
              ? `${runningJobs} active job${runningJobs === 1 ? "" : "s"}`
              : "no active jobs"}
        </small>
      </div>
      <button type="button" className="workspace-context-button" onClick={onOpen}>
        Open activity
      </button>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const searchParams = useSearchParams();
  const route = useMemo(() => getRouteInfo(pathname), [pathname]);
  const isFlow = route.surface === "flow";
  const isAsap7Flow = isFlow && searchParams.get("platform") === "asap7";
  const isImmersiveSurface = isFlow || route.surface === "package" || route.surface === "lab";
  const isAsap7Surface =
    isAsap7Flow ||
    (route.surface === "lab" && searchParams.get("track") !== "course") ||
    (route.surface === "package" && searchParams.get("platform") !== "course");
  const flowHref = isAsap7Surface ? "/flow?platform=asap7" : "/flow";
  const runtimeSurface = isAsap7Flow
    ? "lab"
    : route.surface === "overview" || route.surface === "reference"
      ? "flow"
      : route.surface;
  const [preferences, setPreferences] = useState<LayoutPreferences>(DEFAULT_PREFERENCES);
  const [layoutHydrated, setLayoutHydrated] = useState(false);
  const [compactViewport, setCompactViewport] = useState(false);
  const [mobileViewport, setMobileViewport] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [viewportHeight, setViewportHeight] = useState(0);
  const [focusMode, setFocusMode] = useState(false);
  const previousPreferences = useRef<LayoutPreferences | null>(null);
  const inspectorDrag = useRef<{ startX: number; startWidth: number } | null>(null);
  const dockDrag = useRef<{ startY: number; startHeight: number } | null>(null);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setViewportHeight(window.innerHeight));
    };
    update();
    window.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", update);
    };
  }, []);

  useEffect(() => {
    const initialPreferences = { ...readPreferences() };
    let hasSavedLayout = false;
    try {
      hasSavedLayout = Boolean(window.localStorage.getItem(LAYOUT_STORAGE_KEY));
    } catch {
      // localStorage is optional; use the deterministic defaults below.
    }
    if (!hasSavedLayout && window.matchMedia("(max-width: 767px)").matches) {
      initialPreferences.navigationCollapsed = true;
    }
    setPreferences(initialPreferences);
    setLayoutHydrated(true);
    const media = window.matchMedia("(min-width: 768px) and (max-width: 1599px)");
    const update = () => setCompactViewport(media.matches);
    update();
    media.addEventListener("change", update);
    const mobileMedia = window.matchMedia("(max-width: 767px)");
    const updateMobile = () => {
      setMobileViewport(mobileMedia.matches);
      if (!mobileMedia.matches) setMobileNavOpen(false);
    };
    updateMobile();
    mobileMedia.addEventListener("change", updateMobile);
    return () => {
      media.removeEventListener("change", update);
      mobileMedia.removeEventListener("change", updateMobile);
    };
  }, []);

  useEffect(() => {
    if (mobileViewport) setMobileNavOpen(false);
  }, [pathname, mobileViewport]);

  useEffect(() => {
    if (!layoutHydrated) return;
    try {
      window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(preferences));
    } catch {
      // Layout persistence is an enhancement; the workspace remains usable if storage is unavailable.
    }
  }, [layoutHydrated, preferences]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (mobileNavOpen) {
        setMobileNavOpen(false);
        return;
      }
      if (focusMode) {
        const restore = previousPreferences.current;
        if (restore) setPreferences(restore);
        previousPreferences.current = null;
        setFocusMode(false);
        return;
      }
      if (preferences.inspectorOpen) {
        setPreferences((current) => ({ ...current, inspectorOpen: false }));
      } else if (preferences.dockOpen) {
        setPreferences((current) => ({ ...current, dockOpen: false }));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [focusMode, mobileNavOpen, preferences.dockOpen, preferences.inspectorOpen]);

  function enterFocusMode() {
    if (!focusMode) previousPreferences.current = preferences;
    setFocusMode(true);
  }

  function exitFocusMode() {
    const restore = previousPreferences.current;
    if (restore) setPreferences(restore);
    previousPreferences.current = null;
    setFocusMode(false);
  }

  function startInspectorResize(event: React.PointerEvent<HTMLDivElement>) {
    inspectorDrag.current = {
      startX: event.clientX,
      startWidth: preferences.inspectorWidth,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveInspectorResize(event: React.PointerEvent<HTMLDivElement>) {
    const drag = inspectorDrag.current;
    if (!drag) return;
    setPreferences((current) => ({
      ...current,
      inspectorWidth: clampInspectorWidth(drag.startWidth + drag.startX - event.clientX),
    }));
  }

  function finishInspectorResize() {
    inspectorDrag.current = null;
  }

  function startDockResize(event: React.PointerEvent<HTMLDivElement>) {
    dockDrag.current = {
      startY: event.clientY,
      startHeight: preferences.dockHeight,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveDockResize(event: React.PointerEvent<HTMLDivElement>) {
    const drag = dockDrag.current;
    if (!drag) return;
    const maxHeight = getDockMaximum(
      typeof window === "undefined" ? 0 : window.innerHeight,
      isImmersiveSurface,
    );
    setPreferences((current) => ({
      ...current,
      dockHeight: Math.min(
        Math.max(160, maxHeight),
        Math.max(160, Math.round(drag.startHeight + drag.startY - event.clientY)),
      ),
    }));
  }

  function finishDockResize() {
    dockDrag.current = null;
  }

  const navigationCollapsed =
    focusMode ||
    compactViewport ||
    (mobileViewport ? !mobileNavOpen : preferences.navigationCollapsed);
  const inspectorOpen = !focusMode && preferences.inspectorOpen;
  // Keep the saved dock preference intact so it returns after a viewport
  // resize, but cap the effective height to preserve the workbench.
  const dockMaximum = getDockMaximum(viewportHeight, isImmersiveSurface);
  const effectiveDockHeight = Math.min(preferences.dockHeight, dockMaximum);
  const dockOpen = !focusMode && preferences.dockOpen && dockMaximum >= 160;

  return (
    <div
      className={clsx(
        "app-shell",
        navigationCollapsed && "is-navigation-collapsed",
        inspectorOpen && "is-inspector-open",
        dockOpen && "is-dock-open",
        focusMode && "is-focus-mode",
        isFlow && "is-flow-surface",
        isImmersiveSurface && "is-immersive-surface",
      )}
      style={{
        "--app-nav-width": navigationCollapsed ? "56px" : "224px",
        "--app-inspector-width": `${preferences.inspectorWidth}px`,
        "--app-dock-height": `${effectiveDockHeight}px`,
      } as React.CSSProperties}
    >
      <SiteNav
        collapsed={navigationCollapsed}
        flowHref={flowHref}
        onToggle={
          mobileViewport
            ? () => setMobileNavOpen((open) => !open)
            : compactViewport
              ? undefined
              : () => setPreferences((current) => ({ ...current, navigationCollapsed: !current.navigationCollapsed }))
        }
      />
      <div className="app-main">
        <RuntimeStatusBar surface={runtimeSurface} />
        <header className="workspace-context-bar">
          <div className="workspace-context-copy">
            <span className="workspace-context-kicker">PDflow / {route.label}</span>
            <strong>{route.title}</strong>
            <span className="workspace-context-mode">Linux · local agent</span>
          </div>
          <div className="workspace-context-actions">
            <button
              type="button"
              className={clsx("workspace-context-button", inspectorOpen && "is-active")}
              aria-pressed={inspectorOpen}
              onClick={() => setPreferences((current) => ({ ...current, inspectorOpen: !current.inspectorOpen }))}
            >
              {inspectorOpen ? <PanelRightClose size={15} aria-hidden="true" /> : <PanelRightOpen size={15} aria-hidden="true" />}
              Inspector
            </button>
            <button
              type="button"
              className={clsx("workspace-context-button", dockOpen && "is-active")}
              aria-pressed={dockOpen}
              onClick={() => setPreferences((current) => ({ ...current, dockOpen: !current.dockOpen }))}
            >
              <TerminalSquare size={15} aria-hidden="true" />
              Runtime
            </button>
            <button
              type="button"
              className={clsx("workspace-context-button workspace-focus-button", focusMode && "is-active")}
              aria-pressed={focusMode}
              onClick={focusMode ? exitFocusMode : enterFocusMode}
              title={focusMode ? "Exit focus mode (Esc)" : "Focus the design workspace"}
            >
              <PanelLeftClose size={15} aria-hidden="true" />
              {focusMode ? "Exit focus" : "Focus"}
            </button>
            {mobileViewport && navigationCollapsed && !focusMode && (
              <button
                type="button"
                className="workspace-context-button workspace-nav-open"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Expand application navigation"
                title="Expand navigation"
              >
                <PanelLeftOpen size={15} aria-hidden="true" />
              </button>
            )}
          </div>
        </header>
        <div className="app-content-region">
          <div id="main" className="app-workspace">
            {children}
          </div>
          {inspectorOpen && (
            <>
              <div
                className="workspace-resize-handle workspace-inspector-resizer"
                role="separator"
                tabIndex={0}
                aria-label="Resize context inspector"
                aria-orientation="vertical"
                aria-valuemin={280}
                aria-valuemax={420}
                aria-valuenow={preferences.inspectorWidth}
                onPointerDown={startInspectorResize}
                onPointerMove={moveInspectorResize}
                onPointerUp={finishInspectorResize}
                onPointerCancel={finishInspectorResize}
                onKeyDown={(event) => {
                  if (event.key === "ArrowLeft") {
                    event.preventDefault();
                    setPreferences((current) => ({ ...current, inspectorWidth: clampInspectorWidth(current.inspectorWidth + 16) }));
                  } else if (event.key === "ArrowRight") {
                    event.preventDefault();
                    setPreferences((current) => ({ ...current, inspectorWidth: clampInspectorWidth(current.inspectorWidth - 16) }));
                  } else if (event.key === "Home") {
                    event.preventDefault();
                    setPreferences((current) => ({ ...current, inspectorWidth: 280 }));
                  } else if (event.key === "End") {
                    event.preventDefault();
                    setPreferences((current) => ({ ...current, inspectorWidth: 420 }));
                  }
                }}
              />
              <ContextInspector
                label={isFlow ? "FlowLab" : route.label}
                title={isFlow ? "FlowLab context" : route.title}
                pathname={pathname}
                onClose={() => setPreferences((current) => ({ ...current, inspectorOpen: false }))}
                onReset={() => setPreferences({ ...DEFAULT_PREFERENCES })}
              />
            </>
          )}
        </div>
        {focusMode ? null : dockOpen ? (
          <>
            <div
              className="workspace-resize-handle workspace-dock-resizer"
              role="separator"
              tabIndex={0}
              aria-label="Resize runtime dock"
              aria-orientation="horizontal"
              aria-valuemin={160}
              aria-valuemax={dockMaximum}
              aria-valuenow={effectiveDockHeight}
              onPointerDown={startDockResize}
              onPointerMove={moveDockResize}
              onPointerUp={finishDockResize}
              onPointerCancel={finishDockResize}
              onKeyDown={(event) => {
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setPreferences((current) => ({ ...current, dockHeight: Math.min(dockMaximum, effectiveDockHeight + 16) }));
                } else if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setPreferences((current) => ({ ...current, dockHeight: Math.max(160, effectiveDockHeight - 16) }));
                } else if (event.key === "Home") {
                  event.preventDefault();
                  setPreferences((current) => ({ ...current, dockHeight: 160 }));
                } else if (event.key === "End") {
                  event.preventDefault();
                  setPreferences((current) => ({ ...current, dockHeight: dockMaximum }));
                }
              }}
            />
            <WorkspaceDock onClose={() => setPreferences((current) => ({ ...current, dockOpen: false }))} />
          </>
        ) : (
          <WorkspaceDockRail onOpen={() => setPreferences((current) => ({ ...current, dockOpen: true }))} />
        )}
      </div>
      <CommandPalette />
    </div>
  );
}

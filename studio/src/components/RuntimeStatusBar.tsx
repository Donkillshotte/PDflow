"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { startDesktopAgent } from "@/lib/desktopBridge";
import type {
  AgentEvent,
  AgentHealth,
  RunContext,
  Surface,
  ToolDescriptor,
} from "@/lib/pdflowContracts";

function formatGiB(value?: number | null): string | null {
  if (!Number.isFinite(value) || !value) return null;
  return `${(value / 1024 ** 3).toFixed(1)} GiB`;
}

function statusTone(online: boolean, toolsReady: number): string {
  if (!online) return "runtime-chip-gap";
  if (toolsReady === 0) return "runtime-chip-warn";
  return "runtime-chip-ok";
}

export function RuntimeStatusBar({ surface = "flow" }: { surface?: Surface }) {
  const [health, setHealth] = useState<AgentHealth | null>(null);
  const [context, setContext] = useState<RunContext | null>(null);
  const [tools, setTools] = useState<ToolDescriptor[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [eventLabel, setEventLabel] = useState("connecting…");
  const cursor = useRef(0);

  const refresh = useCallback(async (signal: AbortSignal) => {
    try {
      const [healthResponse, contextResponse, registryResponse] =
        await Promise.all([
          fetch("/api/agent/health", { cache: "no-store", signal }),
          fetch(`/api/context?surface=${encodeURIComponent(surface)}`, { cache: "no-store", signal }),
          fetch("/api/registry", { cache: "no-store", signal }),
      ]);
      if (signal.aborted) return;
      if (healthResponse.ok) {
        const nextHealth = (await healthResponse.json()) as AgentHealth;
        if (signal.aborted) return;
        setHealth(nextHealth);
        window.dispatchEvent(
          new CustomEvent("pdflow:runtime-health", { detail: nextHealth }),
        );
      } else {
        setHealth(null);
      }
      if (contextResponse.ok) {
        const nextContext = (await contextResponse.json()) as RunContext;
        if (signal.aborted) return;
        setContext(nextContext);
      }
      if (registryResponse.ok) {
        const data = (await registryResponse.json()) as { tools?: ToolDescriptor[] };
        if (signal.aborted) return;
        setTools(data.tools || []);
      }
    } catch {
      if (signal.aborted) return;
      // The browser can render while Tauri/agent startup is still in flight.
      // Keep the status chip in GAP and let the polling loop recover silently.
      setHealth(null);
    } finally {
      if (!signal.aborted) setLoaded(true);
    }
  }, [surface]);

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    let connected = false;
    let refreshTimer: number | undefined;
    let pollTimer: number | undefined;
    let labelTimer: number | undefined;
    let refreshInFlight = false;
    let refreshPending = false;
    let pendingLabel: string | undefined;

    const runRefresh = async () => {
      if (disposed) return;
      refreshInFlight = true;
      try {
        await refresh(controller.signal);
      } finally {
        refreshInFlight = false;
        if (refreshPending) {
          refreshPending = false;
          scheduleRefresh();
        }
      }
    };

    const scheduleRefresh = () => {
      if (disposed) return;
      if (refreshInFlight) {
        refreshPending = true;
        return;
      }
      if (refreshTimer !== undefined) return;
      refreshTimer = window.setTimeout(() => {
        refreshTimer = undefined;
        void runRefresh();
      }, 500);
    };

    const scheduleLabel = (label: string) => {
      pendingLabel = label;
      if (labelTimer !== undefined) return;
      labelTimer = window.setTimeout(() => {
        labelTimer = undefined;
        if (pendingLabel) {
          setEventLabel(pendingLabel);
          pendingLabel = undefined;
        }
      }, 250);
    };

    void startDesktopAgent();
    void runRefresh();
    const schedulePoll = () => {
      if (disposed) return;
      pollTimer = window.setTimeout(() => {
        pollTimer = undefined;
        if (!connected) scheduleRefresh();
        schedulePoll();
      }, document.visibilityState === "visible" ? 5000 : 30000);
    };
    const onVisibilityChange = () => {
      if (pollTimer !== undefined) window.clearTimeout(pollTimer);
      pollTimer = undefined;
      schedulePoll();
    };
    schedulePoll();
    document.addEventListener("visibilitychange", onVisibilityChange);
    let retryTimer: number | undefined;
    let retryDelay = 1000;
    let source: EventSource | undefined;
    const connect = () => {
      if (disposed) return;
      const since = cursor.current > 0 ? String(cursor.current) : "latest";
      source = new EventSource(
        "/api/events?since=" + encodeURIComponent(since),
      );
      source.onopen = () => {
        connected = true;
        retryDelay = 1000;
        scheduleRefresh();
        setEventLabel("event stream · connected");
      };
      source.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as AgentEvent;
          cursor.current = Math.max(cursor.current, event.event_id || 0);
          scheduleLabel(event.type.replaceAll(".", " · "));
          window.dispatchEvent(
            new CustomEvent("pdflow:agent-event", { detail: event }),
          );
          scheduleRefresh();
        } catch {
          scheduleLabel("event stream · invalid payload");
        }
      };
      source.onerror = () => {
        connected = false;
        source?.close();
        source = undefined;
        if (disposed) return;
        setEventLabel("polling fallback · reconnecting");
        retryTimer = window.setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 10000);
      };
    };
    connect();
    return () => {
      disposed = true;
      controller.abort();
      if (pollTimer !== undefined) window.clearTimeout(pollTimer);
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      if (refreshTimer !== undefined) window.clearTimeout(refreshTimer);
      if (labelTimer !== undefined) window.clearTimeout(labelTimer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      source?.close();
    };
  }, [refresh, surface]);

  const online = Boolean(health?.ok);
  const ready = tools.filter((tool) => tool.availability === "READY").length;
  const finishCount = context?.finish.length ?? 0;
  const candidateCount = context?.candidates.length ?? 0;
  const contextLabel = context
    ? `${context.design_id} · ${context.pdk_id} · ${context.surface}`
    : "context loading…";
  const authorityLabel = context
    ? context.finish_mutable
      ? "FINISH · EDITABLE"
      : candidateCount > 0
        ? `FINISH · READ ONLY · ${candidateCount} candidate${candidateCount === 1 ? "" : "s"}`
        : "FINISH · READ ONLY"
    : "CONTEXT LOADING";

  return (
    <section className="runtime-status-bar" aria-label="PDflow runtime status">
      <div className={clsx("runtime-chip", loaded ? statusTone(online, ready) : "runtime-chip-warn")}>
        <span className="runtime-dot" aria-hidden="true" />
        {!loaded ? "AGENT CONNECTING" : online ? "LOCAL AGENT" : "AGENT GAP"}
      </div>
      <span className="runtime-context">{contextLabel}</span>
      <span className="runtime-lock">{authorityLabel}</span>
      <span className="runtime-detail">
        {finishCount} finish artifacts · {ready}/{tools.length || "–"} tools
      </span>
      {health?.resources && (
        <span className="runtime-detail">
          heavy slot · {formatGiB(health.resources.limits?.memory_max_bytes) ?? "—"} cap
        </span>
      )}
      <span className="runtime-event" title={eventLabel}>
        {eventLabel}
      </span>
    </section>
  );
}

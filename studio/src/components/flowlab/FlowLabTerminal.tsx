"use client";

import clsx from "clsx";
import { Copy, Download, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useToast } from "@/components/ToastProvider";
import {
  collapseOrfsLines,
  digestOrfsLog,
  type DisplayLine,
} from "@/lib/orfsLog";

function severityClass(sev: string, noise?: boolean) {
  if (sev === "error") return "fl-log-err";
  if (sev === "warn") return noise ? "fl-log-noise" : "fl-log-warn";
  if (sev === "ok") return "fl-log-ok";
  if (sev === "info") return "fl-log-info";
  return "";
}

function renderDisplay(items: DisplayLine[]) {
  return items.map((item) => {
    if (item.kind === "collapse") {
      return (
        <div
          key={`c-${item.index}`}
          className={clsx(
            "fl-log-line fl-log-collapse",
            severityClass(item.severity, item.noise),
          )}
          title={item.sample}
        >
          <span className="fl-log-ln">⋯</span>
          <span className="fl-log-txt">
            [{item.code}] ×{item.count}
            {item.noise ? " · expected nangate45/ORFS noise" : ""}
            {" — "}
            {item.sample.slice(0, 90)}
            {item.sample.length > 90 ? "…" : ""}
          </span>
        </div>
      );
    }
    const { line, index } = item;
    return (
      <div
        key={index}
        className={clsx(
          "fl-log-line",
          severityClass(line.severity, line.noise),
        )}
      >
        <span className="fl-log-ln">{index + 1}</span>
        <span className="fl-log-txt">{line.text || " "}</span>
      </div>
    );
  });
}

const LOG_ROW_HEIGHT = 20;
const MAX_MOUNTED_LOG_ROWS = 200;

function VirtualLog({
  display,
  logRef,
}: {
  display: DisplayLine[];
  logRef: React.RefObject<HTMLDivElement | null>;
}) {
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(320);
  const rowCount = display.length;
  const visibleRows = Math.min(
    MAX_MOUNTED_LOG_ROWS,
    Math.max(1, Math.ceil(viewportHeight / LOG_ROW_HEIGHT) + 24),
  );
  const first = Math.max(
    0,
    Math.min(
      Math.floor(scrollTop / LOG_ROW_HEIGHT) - 12,
      Math.max(0, rowCount - visibleRows),
    ),
  );
  const last = Math.min(rowCount, first + visibleRows);

  useEffect(() => {
    const element = logRef.current;
    if (!element) return;
    setScrollTop(element.scrollTop);
    setViewportHeight(element.clientHeight || 320);
  }, [display, logRef]);

  return (
    <div
      className="fl-terminal-body"
      ref={logRef}
      aria-live="polite"
      onScroll={(event) => {
        setScrollTop(event.currentTarget.scrollTop);
        setViewportHeight(event.currentTarget.clientHeight || 320);
      }}
    >
      <div className="fl-log-virtual-spacer" style={{ height: first * LOG_ROW_HEIGHT }} />
      {renderDisplay(display.slice(first, last))}
      <div
        className="fl-log-virtual-spacer"
        style={{ height: Math.max(0, rowCount - last) * LOG_ROW_HEIGHT }}
      />
    </div>
  );
}

export function FlowLabTerminal({
  log,
  running,
  ok,
  elapsed,
  command,
  blockMsg,
  onExport,
  onClear,
  logRef,
}: {
  log: string;
  running: boolean;
  ok: boolean | null;
  elapsed: string;
  command: string;
  blockMsg: string | null;
  onExport: () => void;
  onClear: () => void;
  logRef: React.RefObject<HTMLDivElement | null>;
}) {
  const { push } = useToast();
  const display = useMemo(() => collapseOrfsLines(log), [log]);
  const digest = useMemo(() => (log ? digestOrfsLog(log) : null), [log]);
  const empty = !log && !running;

  async function copyLog() {
    try {
      await navigator.clipboard.writeText(log || "");
      push("Log copied", "ok");
    } catch {
      push("Copy not available", "bad");
    }
  }

  return (
    <div className="fl-terminal">
      <div className="fl-terminal-bar">
        <div className="fl-terminal-dots" aria-hidden>
          <i />
          <i />
          <i />
        </div>
        <span className="fl-terminal-title">Output · make ORFS</span>
        <div className="fl-terminal-actions">
          {ok !== null && (
            <span className={clsx("fl-status-pill", ok ? "ok" : "bad")}>
              {ok ? "success" : "failed"}
            </span>
          )}
          {running && <span className="fl-status-pill run">{elapsed}</span>}
          <button type="button" className="fl-icon-btn" onClick={copyLog} title="Copy log">
            <Copy size={14} />
          </button>
          <button type="button" className="fl-icon-btn" onClick={onClear} title="Clear">
            <Trash2 size={14} />
          </button>
          <button type="button" className="fl-icon-btn" onClick={onExport} title="Export">
            <Download size={14} />
          </button>
        </div>
      </div>
      {command && (
        <div className="fl-terminal-cmd">
          <span>$</span>
          <code>{command}</code>
        </div>
      )}
      {blockMsg && <p className="fl-block-msg">{blockMsg}</p>}
      {digest && log && (
        <div
          className={clsx(
            "fl-log-digest",
            digest.healthy ? "ok" : "bad",
          )}
          role="status"
        >
          <strong>
            {digest.errors} ERROR · {digest.warnings} WARNING
            {digest.noiseWarnings > 0
              ? ` (${digest.noiseWarnings} noise)`
              : ""}
          </strong>
          <span>{digest.summary}</span>
          {digest.noteworthy.length > 0 && (
            <ul>
              {digest.noteworthy.map((n) => (
                <li key={n.code}>
                  <code>{n.code}</code> ×{n.count} — review against the current run
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {empty ? (
        <div className="fl-terminal-body" ref={logRef} data-empty>
          <div className="fl-terminal-empty">
            <p>
              Press <kbd>Ctrl</kbd>+<kbd>Enter</kbd> or Run phase to start.
            </p>
            <p className="muted">
              stdout/stderr stream will appear here. Expected ORFS WARNINGs are no longer
              highlighted as errors.
            </p>
          </div>
        </div>
      ) : running && !log ? (
        <div className="fl-terminal-body" ref={logRef} data-empty>
          <div className="fl-terminal-empty">
            <p className="fl-pulse">Connecting to stream…</p>
          </div>
        </div>
      ) : (
        <VirtualLog display={display} logRef={logRef} />
      )}
    </div>
  );
}

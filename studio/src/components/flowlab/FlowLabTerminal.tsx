"use client";

import clsx from "clsx";
import { Copy, Download, Trash2 } from "lucide-react";
import { useMemo } from "react";
import { useToast } from "@/components/ToastProvider";

function highlightLog(text: string) {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    let cls = "fl-log-line";
    if (/error|fail|fatal/i.test(line)) cls += " fl-log-err";
    else if (/warn/i.test(line)) cls += " fl-log-warn";
    else if (/^\s*\[\d/.test(line) || /INFO|Done|Success/i.test(line))
      cls += " fl-log-ok";
    return (
      <div key={i} className={cls}>
        <span className="fl-log-ln">{i + 1}</span>
        <span className="fl-log-txt">{line || " "}</span>
      </div>
    );
  });
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
  const lines = useMemo(() => highlightLog(log), [log]);
  const empty = !log && !running;

  async function copyLog() {
    try {
      await navigator.clipboard.writeText(log || "");
      push("Log copiato", "ok");
    } catch {
      push("Copia non disponibile", "bad");
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
          <button type="button" className="fl-icon-btn" onClick={copyLog} title="Copia log">
            <Copy size={14} />
          </button>
          <button type="button" className="fl-icon-btn" onClick={onClear} title="Pulisci">
            <Trash2 size={14} />
          </button>
          <button type="button" className="fl-icon-btn" onClick={onExport} title="Esporta">
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
      <div
        className="fl-terminal-body"
        ref={logRef}
        aria-live="polite"
        data-empty={empty || undefined}
      >
        {empty ? (
          <div className="fl-terminal-empty">
            <p>Premi <kbd>Ctrl</kbd>+<kbd>Enter</kbd> o «Esegui fase» per avviare.</p>
            <p className="muted">Lo stream stdout/stderr apparirà qui in tempo reale.</p>
          </div>
        ) : running && !log ? (
          <div className="fl-terminal-empty">
            <p className="fl-pulse">Connessione allo stream…</p>
          </div>
        ) : (
          lines
        )}
      </div>
    </div>
  );
}

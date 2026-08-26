"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

type StreamEvent =
  | { type: "start"; jobId: string; command: string; action: string }
  | { type: "stdout"; chunk: string }
  | { type: "stderr"; chunk: string }
  | { type: "done"; ok: boolean; code: number | null; ms: number }
  | { type: "error"; message: string };

const STAGE_ACTIONS = [
  { id: "check", label: "Verifica toolchain", hint: "openroad · yosys · sta · klayout" },
  { id: "status", label: "Progresso corso", hint: "lezioni completate" },
  { id: "synth", label: "Esegui synth", hint: "~30s" },
  { id: "floorplan", label: "Esegui floorplan", hint: "die / PDN" },
  { id: "place", label: "Esegui place", hint: "GP → DP" },
  { id: "cts", label: "Esegui CTS", hint: "minuti" },
  { id: "route", label: "Esegui route", hint: "lungo" },
  { id: "finish", label: "Esegui finish", hint: "GDS + SPEF" },
] as const;

function formatMs(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function LiveRunConsole({
  defaultAction,
  compact,
  onFinished,
}: {
  defaultAction?: string;
  compact?: boolean;
  onFinished?: (ok: boolean, action: string) => void;
}) {
  const [action, setAction] = useState(defaultAction ?? "check");
  const [running, setRunning] = useState(false);
  const [ok, setOk] = useState<boolean | null>(null);
  const [log, setLog] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [command, setCommand] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLPreElement | null>(null);
  const tickRef = useRef<number | null>(null);

  useEffect(() => {
    if (defaultAction) setAction(defaultAction);
  }, [defaultAction]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [log]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (tickRef.current) window.clearInterval(tickRef.current);
    };
  }, []);

  async function cancel() {
    if (jobId) {
      await fetch("/api/run/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId }),
      }).catch(() => undefined);
    }
    abortRef.current?.abort();
  }

  async function run(a = action) {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setRunning(true);
    setOk(null);
    setLog("");
    setJobId(null);
    setCommand("");
    setElapsed(0);
    const t0 = Date.now();
    if (tickRef.current) window.clearInterval(tickRef.current);
    tickRef.current = window.setInterval(() => setElapsed(Date.now() - t0), 250);

    try {
      const res = await fetch(`/api/run/stream?action=${encodeURIComponent(a)}`, {
        signal: ac.signal,
      });
      if (!res.ok || !res.body) {
        setOk(false);
        setLog(`HTTP ${res.status}`);
        setRunning(false);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let finalOk = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const ev = JSON.parse(line.slice(6)) as StreamEvent;
          if (ev.type === "start") {
            setJobId(ev.jobId);
            setCommand(ev.command);
            setLog((prev) => prev + `$ ${ev.command}\n\n`);
          } else if (ev.type === "stdout" || ev.type === "stderr") {
            setLog((prev) => prev + ev.chunk);
          } else if (ev.type === "error") {
            setLog((prev) => prev + `\n[error] ${ev.message}\n`);
          } else if (ev.type === "done") {
            finalOk = ev.ok;
            setOk(ev.ok);
            setLog(
              (prev) =>
                prev +
                `\n—— fine · exit ${ev.code ?? "?"} · ${formatMs(ev.ms)} ——\n`,
            );
          }
        }
      }
      setRunning(false);
      if (tickRef.current) window.clearInterval(tickRef.current);
      onFinished?.(finalOk, a);
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setLog((prev) => prev + "\n[sessione chiusa]\n");
      } else {
        setOk(false);
        setLog((prev) => prev + `\n${e instanceof Error ? e.message : String(e)}\n`);
      }
      setRunning(false);
      if (tickRef.current) window.clearInterval(tickRef.current);
    }
  }

  return (
    <div className={clsx("run-console", compact && "run-console-compact")}>
      {!compact && (
        <div className="run-actions">
          {STAGE_ACTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={clsx("chip", action === s.id && "chip-active")}
              onClick={() => setAction(s.id)}
              disabled={running}
            >
              <span>{s.label}</span>
              <em>{s.hint}</em>
            </button>
          ))}
        </div>
      )}
      <div className="run-bar">
        {!running ? (
          <button type="button" className="btn-primary" onClick={() => run()}>
            {compact ? `Lancia ${action}` : "Esegui"}
          </button>
        ) : (
          <button type="button" className="btn-danger" onClick={cancel}>
            Annulla
          </button>
        )}
        {running && <span className="pill live">live · {formatMs(elapsed)}</span>}
        {ok === true && <span className="pill ok">OK</span>}
        {ok === false && <span className="pill bad">Errore</span>}
        {command && !running && <span className="mono-hint">{command}</span>}
      </div>
      {(log || running) && (
        <pre className="run-log" ref={logRef} aria-live="polite">
          {log || "In attesa del primo output…"}
          {running && <span className="cursor-blink">▍</span>}
        </pre>
      )}
    </div>
  );
}

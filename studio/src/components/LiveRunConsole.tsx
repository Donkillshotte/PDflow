"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useToast } from "@/components/ToastProvider";
import { digestOrfsLog } from "@/lib/orfsLog";
import { isLongAction } from "@/lib/actions";

type StreamEvent =
  | { type: "start"; jobId: string; command: string; action: string }
  | { type: "stdout"; chunk: string }
  | { type: "stderr"; chunk: string }
  | { type: "done"; ok: boolean; code: number | null; ms: number; status?: string }
  | { type: "error"; message: string }
  | { type: "blocked"; code: string; message: string };

const PIPELINE_ACTIONS = [
  { id: "check", label: "Verifica toolchain", hint: "openroad · yosys · sta · klayout" },
  { id: "rtl_sim", label: "Sim RTL (Icarus)", hint: "GCD + VCD" },
  { id: "status", label: "Progresso corso", hint: "lezioni completate" },
  { id: "synth", label: "Esegui synth", hint: "~30s" },
  { id: "floorplan", label: "Esegui floorplan", hint: "die / PDN" },
  { id: "gridcheck", label: "Gridcheck PDN", hint: "check_power_grid" },
  { id: "place", label: "Esegui place", hint: "GP → DP" },
  { id: "cts", label: "Esegui CTS", hint: "minuti · conferma" },
  { id: "route", label: "Esegui route", hint: "lungo · conferma" },
  { id: "finish", label: "Esegui finish", hint: "GDS · conferma" },
] as const;

/** Post-finish: power chain + signoff (aligned with POST_FINISH_ACTIONS in actions.ts). */
const POST_FINISH_CHIPS = [
  { id: "activity_power", label: "Activity → power", hint: "set_power_activity" },
  { id: "vectorless", label: "Vectorless / dynamic", hint: "Najm + Kouroussis IR" },
  { id: "chip_pdn_ir", label: "Chip IR mesh", hint: "write_pg_spice" },
  { id: "vyges_em_ir", label: "vyges-em-ir", hint: "CG + backward Euler" },
  { id: "dynamic_ir", label: "Dynamic IR I(t)", hint: "A DirectLU current_run · B SA-AMG" },
  { id: "dse", label: "DSE fisico-aware", hint: "e-graph · BOiLS · oracolo IR" },
  { id: "system_pdn", label: "System PDN", hint: "VRM→board→pkg→die" },
  { id: "power_chain", label: "Catena SPICE", hint: "activity→IR→system" },
  { id: "export_spice_lab", label: "Export SPICE lab", hint: "sim/spice/" },
  { id: "sta_signoff", label: "STA signoff", hint: "timing vs golden" },
  { id: "drc_signoff", label: "DRC signoff", hint: "route + GDS DRC" },
  { id: "klayout_lvs", label: "LVS signoff", hint: "GDS vs netlist" },
  { id: "power_signoff", label: "Power signoff", hint: "IR/droop/Zmax" },
  { id: "signoff_all", label: "Signoff completo", hint: "4 pilastri · lungo" },
  { id: "thermal_signoff", label: "Thermal proxy", hint: "IR+droop Fase 2" },
  { id: "pkg_signoff", label: "PKG signoff", hint: "bump/RDL/system" },
  { id: "signoff_phase2", label: "Signoff Fase 2", hint: "thermal + PKG" },
  { id: "yosys_equiv", label: "Yosys equiv", hint: "EQY-class RTL↔synth" },
  { id: "formal_gcd", label: "Formal SAT", hint: "sby-class tempinduct" },
  { id: "openrcx_report", label: "OpenRCX SPEF", hint: "6_final.spef" },
  { id: "analytical_pex", label: "PEX analitico", hint: "FasterCap-class FDM" },
  { id: "layout_tools", label: "Magic / Netgen probe", hint: "no FreePDK45 tech" },
  { id: "tool_matrix", label: "Tool matrix", hint: "tutti i check OSS" },
] as const;

const STAGE_ACTIONS = [...PIPELINE_ACTIONS, ...POST_FINISH_CHIPS];

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
  const { push } = useToast();
  const [action, setAction] = useState(defaultAction ?? "check");
  const [running, setRunning] = useState(false);
  const [ok, setOk] = useState<boolean | null>(null);
  const [log, setLog] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [command, setCommand] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [blockMsg, setBlockMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLPreElement | null>(null);
  const tickRef = useRef<number | null>(null);
  const lastActionRef = useRef(action);
  const digest = useMemo(() => (log ? digestOrfsLog(log) : null), [log]);

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

  function exportLog() {
    const blob = new Blob([log || "(vuoto)"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `run-${lastActionRef.current}-${Date.now()}.log`;
    a.click();
    URL.revokeObjectURL(url);
    push("Log esportato", "ok");
  }

  async function cancel() {
    if (jobId) {
      await fetch("/api/run/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId }),
      }).catch(() => undefined);
    }
    abortRef.current?.abort();
    push("Job annullato", "info");
  }

  function requestRun(a = action) {
    if (running) return;
    if (isLongAction(a)) {
      setPendingAction(a);
      setConfirmOpen(true);
      return;
    }
    void run(a);
  }

  async function run(a = action) {
    lastActionRef.current = a;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setRunning(true);
    setOk(null);
    setLog("");
    setJobId(null);
    setCommand("");
    setBlockMsg(null);
    setElapsed(0);
    const t0 = Date.now();
    if (tickRef.current) window.clearInterval(tickRef.current);
    tickRef.current = window.setInterval(() => setElapsed(Date.now() - t0), 250);

    try {
      const res = await fetch(`/api/run/stream?action=${encodeURIComponent(a)}`, {
        signal: ac.signal,
      });
      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          msg = body.error || msg;
        } catch {
          /* ignore */
        }
        setOk(false);
        setBlockMsg(msg);
        setLog(msg);
        setRunning(false);
        push(msg, "bad");
        if (tickRef.current) window.clearInterval(tickRef.current);
        onFinished?.(false, a);
        return;
      }
      if (!res.body) {
        setOk(false);
        setLog("Nessun body SSE");
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
          } else if (ev.type === "blocked") {
            setBlockMsg(ev.message);
            setLog((prev) => prev + `\n[blocked] ${ev.message}\n`);
            push(ev.message, "bad");
          } else if (ev.type === "done") {
            finalOk = ev.ok;
            setOk(ev.ok);
            setLog(
              (prev) =>
                prev +
                `\n—— fine · ${ev.status ?? (ev.ok ? "ok" : "error")} · exit ${ev.code ?? "?"} · ${formatMs(ev.ms)} ——\n`,
            );
            push(
              ev.ok ? `${a} completato` : `${a} fallito (exit ${ev.code})`,
              ev.ok ? "ok" : "bad",
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
        setOk(false);
      } else {
        setOk(false);
        setLog((prev) => prev + `\n${e instanceof Error ? e.message : String(e)}\n`);
        push("Errore di rete sul run", "bad");
      }
      setRunning(false);
      if (tickRef.current) window.clearInterval(tickRef.current);
      onFinished?.(false, a);
    }
  }

  return (
    <div className={clsx("run-console", compact && "run-console-compact")}>
      {!compact && (
        <div className="run-actions" role="group" aria-label="Azioni pipeline">
          {STAGE_ACTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={clsx("chip", action === s.id && "chip-active")}
              onClick={() => setAction(s.id)}
              disabled={running}
              aria-pressed={action === s.id}
            >
              <span>{s.label}</span>
              <em>{s.hint}</em>
            </button>
          ))}
        </div>
      )}
      <div className="run-bar">
        {!running ? (
          <>
            <button type="button" className="btn-primary" onClick={() => requestRun()}>
              {compact ? `Lancia ${action}` : "Esegui"}
            </button>
            {ok === false && (
              <button
                type="button"
                className="btn-ghost"
                onClick={() => requestRun(lastActionRef.current)}
              >
                Riprova
              </button>
            )}
            {log && (
              <button type="button" className="btn-ghost" onClick={exportLog}>
                Export log
              </button>
            )}
          </>
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
      {blockMsg && (
        <p className="block-banner" role="alert">
          {blockMsg}
        </p>
      )}
      {digest && log && (
        <p
          className={clsx("run-digest", digest.healthy ? "ok" : "bad")}
          role="status"
        >
          {digest.summary}
        </p>
      )}
      {(log || running) && (
        <pre className="run-log" ref={logRef} aria-live="polite" tabIndex={0}>
          {log || "In attesa del primo output…"}
          {running && <span className="cursor-blink">▍</span>}
        </pre>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title={`Confermare ${pendingAction}?`}
        body="Questa fase può richiedere diversi minuti e tiene il lock della pipeline. Continua solo se le dipendenze precedenti sono complete."
        confirmLabel="Avvia comunque"
        danger
        onCancel={() => {
          setConfirmOpen(false);
          setPendingAction(null);
        }}
        onConfirm={() => {
          const a = pendingAction;
          setConfirmOpen(false);
          setPendingAction(null);
          if (a) void run(a);
        }}
      />
    </div>
  );
}

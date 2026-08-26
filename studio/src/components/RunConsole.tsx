"use client";

import { useState } from "react";
import clsx from "clsx";

type RunState = {
  running: boolean;
  ok: boolean | null;
  log: string;
  command?: string;
};

const STAGE_ACTIONS = [
  { id: "check", label: "Verifica toolchain", hint: "openroad · yosys · sta · klayout" },
  { id: "status", label: "Progresso corso", hint: "lezioni completate" },
  { id: "synth", label: "Esegui synth", hint: "FLOW_VARIANT=learn · ~30s" },
  { id: "floorplan", label: "Esegui floorplan", hint: "die / PDN" },
  { id: "place", label: "Esegui place", hint: "GP → resize → DP" },
  { id: "cts", label: "Esegui CTS", hint: "può richiedere minuti" },
  { id: "route", label: "Esegui route", hint: "GRT + DRT · lungo" },
  { id: "finish", label: "Esegui finish", hint: "GDS + SPEF · lungo" },
] as const;

export function RunConsole({
  defaultAction,
  compact,
}: {
  defaultAction?: string;
  compact?: boolean;
}) {
  const [action, setAction] = useState(defaultAction ?? "check");
  const [state, setState] = useState<RunState>({
    running: false,
    ok: null,
    log: "",
  });

  async function run(a = action) {
    setState({ running: true, ok: null, log: "Avvio…\n" });
    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: a }),
      });
      const data = await res.json();
      const log = [data.command, data.stdout, data.stderr].filter(Boolean).join("\n\n");
      setState({
        running: false,
        ok: Boolean(data.ok),
        log,
        command: data.command,
      });
    } catch (e) {
      setState({
        running: false,
        ok: false,
        log: e instanceof Error ? e.message : "Errore di rete",
      });
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
              disabled={state.running}
            >
              <span>{s.label}</span>
              <em>{s.hint}</em>
            </button>
          ))}
        </div>
      )}
      <div className="run-bar">
        <button
          type="button"
          className="btn-primary"
          onClick={() => run()}
          disabled={state.running}
        >
          {state.running ? "In esecuzione…" : compact ? `Lancia ${action}` : "Esegui"}
        </button>
        {state.ok === true && <span className="pill ok">OK</span>}
        {state.ok === false && <span className="pill bad">Errore</span>}
      </div>
      {(state.log || state.running) && (
        <pre className="run-log" aria-live="polite">
          {state.log || "…"}
        </pre>
      )}
    </div>
  );
}

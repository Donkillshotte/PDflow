"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ResultsPanel } from "@/components/ResultsPanel";
import { useToast } from "@/components/ToastProvider";

type FlowlabParams = {
  coreUtilization: number;
  placeDensityAddon: number;
  abcArea: 0 | 1;
  sdcPreset: "default" | "relaxed" | "tight";
  tnsEndPercent: number;
};

type Phase = {
  id: string;
  label: string;
  title: string;
  action: string;
  hint: string;
};

type StageStatus = {
  id: string;
  label: string;
  action: string;
  done: boolean;
  primary?: string;
};

const PHASES: Phase[] = [
  {
    id: "rtl",
    label: "RTL",
    title: "Scrivi e simula RTL",
    action: "rtl_sim",
    hint: "Editor Verilog · Icarus",
  },
  {
    id: "synth",
    label: "Sintesi",
    title: "Sintesi logica (Yosys)",
    action: "synth",
    hint: "ABC · SDC",
  },
  {
    id: "floorplan",
    label: "Floorplan",
    title: "Floorplan e PDN",
    action: "floorplan",
    hint: "Utilizzo core",
  },
  {
    id: "place",
    label: "Place",
    title: "Placement",
    action: "place",
    hint: "Densità",
  },
  {
    id: "cts",
    label: "CTS",
    title: "Clock tree",
    action: "cts",
    hint: "TNS end %",
  },
  {
    id: "route",
    label: "Route",
    title: "Routing",
    action: "route",
    hint: "Global + detailed",
  },
  {
    id: "finish",
    label: "GDSII",
    title: "Finish · GDS",
    action: "finish",
    hint: "SPEF · GDS",
  },
];

const LONG = new Set(["cts", "route", "finish"]);

type StreamEvent =
  | { type: "start"; jobId: string; command: string; action: string }
  | { type: "stdout"; chunk: string }
  | { type: "stderr"; chunk: string }
  | { type: "done"; ok: boolean; code: number | null; ms: number }
  | { type: "error"; message: string }
  | { type: "blocked"; code: string; message: string };

function formatMs(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function FlowLab() {
  const { push } = useToast();
  const [phaseId, setPhaseId] = useState("rtl");
  const [rtl, setRtl] = useState("");
  const [params, setParams] = useState<FlowlabParams>({
    coreUtilization: 35,
    placeDensityAddon: 0.2,
    abcArea: 1,
    sdcPreset: "default",
    tnsEndPercent: 100,
  });
  const [stages, setStages] = useState<StageStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState("");
  const [ok, setOk] = useState<boolean | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [command, setCommand] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [blockMsg, setBlockMsg] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLPreElement | null>(null);
  const tickRef = useRef<number | null>(null);

  const phase = PHASES.find((p) => p.id === phaseId) ?? PHASES[0];
  const resultsStage =
    phase.id === "rtl" ? "synth" : (phase.id as string);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/flowlab");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRtl(data.rtl ?? "");
      setParams(data.params);
      setStages(data.stages ?? []);
      setDirty(false);
    } catch (e) {
      push(e instanceof Error ? e.message : "errore FlowLab", "bad");
    } finally {
      setLoading(false);
    }
  }, [push]);

  useEffect(() => {
    void load();
  }, [load]);

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

  async function saveAll(nextRtl = rtl, nextParams = params) {
    setSaving(true);
    try {
      const res = await fetch("/api/flowlab", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rtl: nextRtl, params: nextParams }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
      setRtl(body.rtl);
      setParams(body.params);
      setStages(body.stages ?? []);
      setDirty(false);
      push("Salvato", "ok");
      return true;
    } catch (e) {
      push(e instanceof Error ? e.message : "salvataggio fallito", "bad");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function resetGolden() {
    setSaving(true);
    try {
      const res = await fetch("/api/flowlab", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resetRtl: true }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "reset fallito");
      setRtl(body.rtl);
      setDirty(false);
      push("RTL ripristinato dal golden", "info");
    } catch (e) {
      push(e instanceof Error ? e.message : "reset fallito", "bad");
    } finally {
      setSaving(false);
    }
  }

  function updateParam<K extends keyof FlowlabParams>(
    key: K,
    value: FlowlabParams[K],
  ) {
    setParams((p) => ({ ...p, [key]: value }));
    setDirty(true);
  }

  async function runAction() {
    if (dirty) {
      const saved = await saveAll();
      if (!saved) return;
    }
    setRunning(true);
    setOk(null);
    setLog("");
    setBlockMsg(null);
    setJobId(null);
    setElapsed(0);
    const started = Date.now();
    if (tickRef.current) window.clearInterval(tickRef.current);
    tickRef.current = window.setInterval(() => {
      setElapsed(Date.now() - started);
    }, 200);

    const q = new URLSearchParams({
      action: phase.action,
      mode: "flowlab",
      coreUtilization: String(params.coreUtilization),
      placeDensityAddon: String(params.placeDensityAddon),
      abcArea: String(params.abcArea),
      sdcPreset: params.sdcPreset,
      tnsEndPercent: String(params.tnsEndPercent),
    });
    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const res = await fetch(`/api/run/stream?${q}`, { signal: ac.signal });
      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({}));
        setBlockMsg(err.error || `HTTP ${res.status}`);
        setOk(false);
        push(err.error || `HTTP ${res.status}`, "bad");
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part
            .split("\n")
            .find((l) => l.startsWith("data: "));
          if (!line) continue;
          const ev = JSON.parse(line.slice(6)) as StreamEvent;
          if (ev.type === "start") {
            setJobId(ev.jobId);
            setCommand(ev.command);
          } else if (ev.type === "stdout" || ev.type === "stderr") {
            setLog((L) => L + ev.chunk);
          } else if (ev.type === "blocked") {
            setBlockMsg(ev.message);
            setOk(false);
            push(ev.message, "bad");
          } else if (ev.type === "error") {
            setLog((L) => L + `\n[error] ${ev.message}\n`);
            setOk(false);
          } else if (ev.type === "done") {
            setOk(ev.ok);
            push(
              ev.ok
                ? `${phase.label} completata · ${formatMs(ev.ms)}`
                : `${phase.label} fallita`,
              ev.ok ? "ok" : "bad",
            );
            if (ev.ok) {
              setRefreshKey((k) => k + 1);
              void load();
            }
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        push(e instanceof Error ? e.message : "run fallito", "bad");
        setOk(false);
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
      if (tickRef.current) {
        window.clearInterval(tickRef.current);
        tickRef.current = null;
      }
    }
  }

  function requestRun() {
    if (LONG.has(phase.action)) {
      setConfirmOpen(true);
      return;
    }
    void runAction();
  }

  async function cancel() {
    if (jobId) {
      await fetch("/api/run/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId }),
      });
    }
    abortRef.current?.abort();
    push("Run annullato", "info");
  }

  if (loading) {
    return <div className="flowlab muted">Carico FlowLab…</div>;
  }

  return (
    <div className="flowlab">
      <header className="page-head">
        <h1>Flusso RTL → GDSII</h1>
        <p>
          Laboratorio funzionale: edita RTL, scegli i parametri di ogni fase e
          lanciala. I risultati vanno in{" "}
          <code>results/…/gcd/flowlab</code> (non toccano il corso).
        </p>
      </header>

      <nav className="flowlab-steps" aria-label="Fasi del flusso">
        {PHASES.map((p) => {
          const st = stages.find((s) => s.id === p.id);
          return (
            <button
              key={p.id}
              type="button"
              className={clsx(
                "flowlab-step",
                phaseId === p.id && "active",
                st?.done && "done",
              )}
              onClick={() => setPhaseId(p.id)}
            >
              <strong>{p.label}</strong>
              <em>{p.hint}</em>
              {st?.done && <span className="pill ok">fatto</span>}
            </button>
          );
        })}
      </nav>

      <section className="panel flowlab-panel">
        <div className="ops-head">
          <div>
            <h2>{phase.title}</h2>
            <p className="muted">
              Azione <code>{phase.action}</code>
              {dirty ? " · modifiche non salvate" : ""}
            </p>
          </div>
          <div className="lesson-actions">
            <button
              type="button"
              className="btn-ghost"
              disabled={saving || running}
              onClick={() => void saveAll()}
            >
              {saving ? "Salvo…" : "Salva"}
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={running}
              onClick={requestRun}
            >
              {running ? `Eseguo… ${formatMs(elapsed)}` : `Esegui ${phase.label}`}
            </button>
            {running && (
              <button type="button" className="btn-ghost" onClick={() => void cancel()}>
                Annulla
              </button>
            )}
          </div>
        </div>

        {phase.id === "rtl" && (
          <div className="flowlab-rtl">
            <div className="lesson-actions" style={{ marginBottom: "0.6rem" }}>
              <span className="pill">learn/flowlab/gcd.v</span>
              <button
                type="button"
                className="btn-ghost"
                disabled={saving || running}
                onClick={() => void resetGolden()}
              >
                Ripristina golden
              </button>
            </div>
            <textarea
              className="rtl-editor"
              spellCheck={false}
              value={rtl}
              onChange={(e) => {
                setRtl(e.target.value);
                setDirty(true);
              }}
              aria-label="Editor RTL Verilog"
              rows={22}
            />
          </div>
        )}

        {phase.id !== "rtl" && (
          <div className="flowlab-params">
            {(phase.id === "synth" || phase.id === "floorplan") && (
              <>
                <label>
                  SDC
                  <select
                    value={params.sdcPreset}
                    onChange={(e) =>
                      updateParam(
                        "sdcPreset",
                        e.target.value as FlowlabParams["sdcPreset"],
                      )
                    }
                  >
                    <option value="default">default (0.46 ns)</option>
                    <option value="relaxed">relaxed (2.0 ns)</option>
                    <option value="tight">tight (0.25 ns)</option>
                  </select>
                </label>
                <label>
                  ABC area mode
                  <select
                    value={params.abcArea}
                    onChange={(e) =>
                      updateParam("abcArea", Number(e.target.value) as 0 | 1)
                    }
                  >
                    <option value={1}>area (ABC_AREA=1)</option>
                    <option value={0}>delay (ABC_AREA=0)</option>
                  </select>
                </label>
              </>
            )}
            {(phase.id === "floorplan" ||
              phase.id === "place" ||
              phase.id === "synth") && (
              <label>
                Core utilization ({params.coreUtilization}%)
                <input
                  type="range"
                  min={20}
                  max={55}
                  step={1}
                  value={params.coreUtilization}
                  onChange={(e) =>
                    updateParam("coreUtilization", Number(e.target.value))
                  }
                />
              </label>
            )}
            {(phase.id === "place" || phase.id === "cts") && (
              <label>
                Place density addon ({params.placeDensityAddon.toFixed(2)})
                <input
                  type="range"
                  min={0.05}
                  max={0.4}
                  step={0.01}
                  value={params.placeDensityAddon}
                  onChange={(e) =>
                    updateParam("placeDensityAddon", Number(e.target.value))
                  }
                />
              </label>
            )}
            {(phase.id === "cts" || phase.id === "route") && (
              <label>
                TNS end percent ({params.tnsEndPercent}%)
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={params.tnsEndPercent}
                  onChange={(e) =>
                    updateParam("tnsEndPercent", Number(e.target.value))
                  }
                />
              </label>
            )}
            {phase.id === "finish" && (
              <p className="muted">
                Finish genera GDS/SPEF/netlist finali con i parametri salvati
                (util {params.coreUtilization}%, SDC {params.sdcPreset}).
              </p>
            )}
            {phase.id === "route" && (
              <p className="muted">
                Routing usa gli artefatti CTS della variante flowlab. Può
                richiedere diversi minuti.
              </p>
            )}
          </div>
        )}

        {blockMsg && <p className="block-banner">{blockMsg}</p>}
        {command && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            <code>{command}</code>
          </p>
        )}
        <pre className="run-log" ref={logRef} aria-live="polite">
          {log || (running ? "In attesa di log…" : "Log del run FlowLab")}
        </pre>
        {ok !== null && (
          <span className={clsx("pill", ok ? "ok" : "bad")}>
            {ok ? "ok" : "errore"}
          </span>
        )}
      </section>

      {phase.id !== "rtl" && (
        <section className="panel" style={{ marginTop: "1.2rem" }}>
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
            Artefatti · {resultsStage} (flowlab)
          </h2>
          <ResultsPanel
            stage={resultsStage}
            variant="flowlab"
            refreshKey={refreshKey}
          />
        </section>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title={`Confermi ${phase.label}?`}
        body={`La fase ${phase.action} può richiedere diversi minuti. Il job è single-flight.`}
        confirmLabel="Esegui"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false);
          void runAction();
        }}
      />
    </div>
  );
}

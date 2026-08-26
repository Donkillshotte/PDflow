"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import clsx from "clsx";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ResultsPanel } from "@/components/ResultsPanel";
import { InspectPanel } from "@/components/InspectPanel";
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
  help: string;
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
    label: "1 · RTL",
    title: "Scrivi e simula RTL",
    action: "rtl_sim",
    hint: "Editor + Icarus",
    help: "Modifica il Verilog, salva, poi simula. Serve per validare la logica prima della sintesi.",
  },
  {
    id: "synth",
    label: "2 · Sintesi",
    title: "Sintesi logica (Yosys)",
    action: "synth",
    hint: "ABC · SDC",
    help: "Scegli vincoli SDC e modalità ABC, poi lancia la sintesi. Produce netlist + ODB.",
  },
  {
    id: "floorplan",
    label: "3 · Floorplan",
    title: "Floorplan e PDN",
    action: "floorplan",
    hint: "Utilizzo core",
    help: "Imposta l’utilizzo del core: più alto = chip più piccolo, più rischio di congestione.",
  },
  {
    id: "place",
    label: "4 · Place",
    title: "Placement",
    action: "place",
    hint: "Densità",
    help: "Global + detailed placement. La densità addon regola lo spazio libero tra le celle.",
  },
  {
    id: "cts",
    label: "5 · CTS",
    title: "Clock tree synthesis",
    action: "cts",
    hint: "TNS %",
    help: "Costruisce l’albero di clock e ripara timing. TNS end % quanto recovery fare.",
  },
  {
    id: "route",
    label: "6 · Route",
    title: "Routing",
    action: "route",
    hint: "Global + detail",
    help: "Instrada i segnali. Può richiedere minuti: conferma prima di lanciare.",
  },
  {
    id: "finish",
    label: "7 · GDSII",
    title: "Finish · GDS",
    action: "finish",
    hint: "SPEF · GDS",
    help: "Genera GDS, SPEF, netlist finale. Apri KLayout o la GUI OpenROAD sui risultati.",
  },
];

const LONG = new Set(["cts", "route", "finish"]);
const PHASE_IDS = PHASES.map((p) => p.id);

type StreamEvent =
  | { type: "start"; jobId: string; command: string; action: string }
  | { type: "stdout"; chunk: string }
  | { type: "stderr"; chunk: string }
  | { type: "done"; ok: boolean; code: number | null; ms: number }
  | { type: "error"; message: string }
  | { type: "blocked"; code: string; message: string };

type RightTab = "log" | "artifacts" | "inspect";

function formatMs(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function phaseUnlocked(id: string, stages: StageStatus[]) {
  const idx = PHASE_IDS.indexOf(id);
  if (idx <= 0) return true;
  const prev = PHASES[idx - 1];
  return Boolean(stages.find((s) => s.id === prev.id)?.done);
}

export function FlowLab() {
  const { push } = useToast();
  const router = useRouter();
  const search = useSearchParams();
  const initialPhase = (() => {
    const q = search.get("phase");
    return q && PHASE_IDS.includes(q) ? q : "rtl";
  })();
  const [phaseId, setPhaseId] = useState(initialPhase);
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
  const [rightTab, setRightTab] = useState<RightTab>("log");
  const [guiBusy, setGuiBusy] = useState(false);
  const [offerNext, setOfferNext] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLPreElement | null>(null);
  const tickRef = useRef<number | null>(null);
  const saveTimer = useRef<number | null>(null);
  const rtlRef = useRef(rtl);
  const paramsRef = useRef(params);
  const urlReady = useRef(false);

  const phase = PHASES.find((p) => p.id === phaseId) ?? PHASES[0];
  const resultsStage = phase.id === "rtl" ? "synth" : phase.id;
  const doneCount = stages.filter((s) => s.done).length;
  const progressPct = Math.round((doneCount / PHASES.length) * 100);
  const unlocked = phaseUnlocked(phaseId, stages);
  const nextPhase = PHASES[PHASE_IDS.indexOf(phaseId) + 1] ?? null;

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/flowlab");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRtl(data.rtl ?? "");
      rtlRef.current = data.rtl ?? "";
      setParams(data.params);
      paramsRef.current = data.params;
      setStages(data.stages ?? []);
      setDirty(false);
      return data;
    } catch (e) {
      push(e instanceof Error ? e.message : "errore FlowLab", "bad");
      return null;
    }
  }, [push]);

  useEffect(() => {
    setLoading(true);
    void load().finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    const q = search.get("phase");
    if (q && PHASE_IDS.includes(q) && q !== phaseId) {
      setPhaseId(q);
    }
    urlReady.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to URL
  }, [search]);

  useEffect(() => {
    if (!urlReady.current) return;
    const current = search.get("phase");
    if (current === phaseId) return;
    router.replace(`/flusso?phase=${phaseId}`, { scroll: false });
  }, [phaseId, router, search]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [log]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (tickRef.current) window.clearInterval(tickRef.current);
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
    };
  }, []);

  const saveAll = useCallback(
    async (
      nextRtl = rtlRef.current,
      nextParams = paramsRef.current,
      quiet = false,
    ) => {
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
        rtlRef.current = body.rtl;
        setParams(body.params);
        paramsRef.current = body.params;
        setStages(body.stages ?? []);
        setDirty(false);
        if (!quiet) push("Salvato", "ok");
        return true;
      } catch (e) {
        push(e instanceof Error ? e.message : "salvataggio fallito", "bad");
        return false;
      } finally {
        setSaving(false);
      }
    },
    [push],
  );

  function scheduleAutosave(nextRtl: string, nextParams: FlowlabParams) {
    setDirty(true);
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      void saveAll(nextRtl, nextParams, true);
    }, 900);
  }

  function onRtlChange(value: string) {
    setRtl(value);
    rtlRef.current = value;
    scheduleAutosave(value, paramsRef.current);
  }

  function updateParam<K extends keyof FlowlabParams>(
    key: K,
    value: FlowlabParams[K],
  ) {
    setParams((p) => {
      const next = { ...p, [key]: value };
      paramsRef.current = next;
      scheduleAutosave(rtlRef.current, next);
      return next;
    });
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
      rtlRef.current = body.rtl;
      setDirty(false);
      push("RTL ripristinato dal golden", "info");
    } catch (e) {
      push(e instanceof Error ? e.message : "reset fallito", "bad");
    } finally {
      setSaving(false);
    }
  }

  async function runAction() {
    if (dirty) {
      const saved = await saveAll(rtlRef.current, paramsRef.current, true);
      if (!saved) return;
    }
    setRunning(true);
    setOk(null);
    setLog("");
    setBlockMsg(null);
    setJobId(null);
    setOfferNext(false);
    setElapsed(0);
    setRightTab("log");
    const started = Date.now();
    if (tickRef.current) window.clearInterval(tickRef.current);
    tickRef.current = window.setInterval(() => {
      setElapsed(Date.now() - started);
    }, 200);

    const p = paramsRef.current;
    const q = new URLSearchParams({
      action: phase.action,
      mode: "flowlab",
      coreUtilization: String(p.coreUtilization),
      placeDensityAddon: String(p.placeDensityAddon),
      abcArea: String(p.abcArea),
      sdcPreset: p.sdcPreset,
      tnsEndPercent: String(p.tnsEndPercent),
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
          const line = part.split("\n").find((l) => l.startsWith("data: "));
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
              setOfferNext(Boolean(nextPhase));
              if (phase.id !== "rtl") setRightTab("artifacts");
              await load();
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
    if (!unlocked) {
      push("Completa prima la fase precedente", "bad");
      return;
    }
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

  async function openGui() {
    if (phase.id === "rtl") return;
    setGuiBusy(true);
    try {
      const catalog = await fetch("/api/open").then((r) => r.json());
      const list = (catalog.targets ?? []) as {
        id: string;
        stage?: string;
        kind: string;
        exists: boolean;
      }[];
      const pick =
        list.find(
          (t) =>
            t.stage === resultsStage && t.kind === "openroad" && t.exists,
        ) ??
        list.find((t) => t.stage === resultsStage && t.exists);
      // Prefer opening by artifact in flowlab variant
      const artRes = await fetch("/api/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          artifact:
            resultsStage === "finish"
              ? "6_final.odb"
              : resultsStage === "synth"
                ? "1_synth.odb"
                : resultsStage === "floorplan"
                  ? "2_floorplan.odb"
                  : resultsStage === "place"
                    ? "3_place.odb"
                    : resultsStage === "cts"
                      ? "4_cts.odb"
                      : "5_route.odb",
          variant: "flowlab",
        }),
      });
      const body = await artRes.json();
      if (body.launched) {
        push(body.message, "ok");
        return;
      }
      if (body.command) {
        await navigator.clipboard?.writeText(body.command).catch(() => undefined);
        push(body.message || "Comando GUI copiato — apri Desktop", "info");
        return;
      }
      if (pick) {
        const res = await fetch("/api/open", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: pick.id }),
        });
        const b = await res.json();
        push(b.message || "Apertura GUI", b.launched ? "ok" : "info");
      } else {
        push(body.message || "Nessuna GUI pronta per questa fase", "bad");
      }
    } finally {
      setGuiBusy(false);
    }
  }

  function exportLog() {
    const blob = new Blob([log || "(vuoto)"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `flowlab-${phase.id}-${Date.now()}.log`;
    a.click();
    URL.revokeObjectURL(url);
    push("Log esportato", "ok");
  }

  const lineCount = useMemo(() => rtl.split("\n").length, [rtl]);

  if (loading) {
    return <div className="flowlab muted">Carico workbench FlowLab…</div>;
  }

  return (
    <div className="flowlab flowlab-workbench">
      <header className="flowlab-hero">
        <div>
          <p className="hero-brand" style={{ fontSize: "0.85rem", margin: 0 }}>
            FlowLab
          </p>
          <h1>RTL → GDSII, interattivo</h1>
          <p>
            Ogni fase è un laboratorio: edita, regola i parametri, lancia, ispeziona
            artefatti e GUI. Variante isolata{" "}
            <code>results/…/gcd/flowlab</code>.
          </p>
        </div>
        <div className="flowlab-progress" aria-label={`Progresso ${progressPct}%`}>
          <strong>{doneCount}/{PHASES.length}</strong>
          <span>fasi complete</span>
          <div className="flowlab-bar">
            <i style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      </header>

      <div className="flowlab-grid">
        <aside className="flowlab-rail" aria-label="Fasi">
          {PHASES.map((p, i) => {
            const st = stages.find((s) => s.id === p.id);
            const open = phaseUnlocked(p.id, stages);
            return (
              <button
                key={p.id}
                type="button"
                disabled={!open && !st?.done}
                className={clsx(
                  "flowlab-rail-item",
                  phaseId === p.id && "active",
                  st?.done && "done",
                  !open && "locked",
                )}
                onClick={() => {
                  if (!open && !st?.done) {
                    push(`Sblocca «${p.label}» completando la fase ${i}`, "info");
                    return;
                  }
                  setPhaseId(p.id);
                  setOfferNext(false);
                  setOk(null);
                }}
              >
                <span className="flowlab-rail-num">{i + 1}</span>
                <span>
                  <strong>{p.label.replace(/^\d+\s·\s/, "")}</strong>
                  <em>{p.hint}</em>
                </span>
                {st?.done ? (
                  <span className="pill ok">ok</span>
                ) : open ? (
                  <span className="pill">apri</span>
                ) : (
                  <span className="pill">lock</span>
                )}
              </button>
            );
          })}
        </aside>

        <section className="panel flowlab-main">
          <div className="ops-head">
            <div>
              <h2>{phase.title}</h2>
              <p className="muted">{phase.help}</p>
            </div>
            <div className="lesson-actions">
              <span className={clsx("pill", dirty ? "bad" : "ok")}>
                {saving ? "autosave…" : dirty ? "non salvato" : "sincronizzato"}
              </span>
              <button
                type="button"
                className="btn-ghost"
                disabled={saving || running}
                onClick={() => void saveAll()}
              >
                Salva ora
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={running || (!unlocked && !stages.find((s) => s.id === phaseId)?.done)}
                onClick={requestRun}
              >
                {running
                  ? `Eseguo… ${formatMs(elapsed)}`
                  : `Esegui ${phase.label.replace(/^\d+\s·\s/, "")}`}
              </button>
              {running && (
                <button type="button" className="btn-ghost" onClick={() => void cancel()}>
                  Annulla
                </button>
              )}
            </div>
          </div>

          {!unlocked && (
            <p className="block-banner">
              Fase bloccata: completa prima «{PHASES[PHASE_IDS.indexOf(phaseId) - 1]?.label}».
            </p>
          )}

          {phase.id === "rtl" ? (
            <div className="flowlab-rtl">
              <div className="lesson-actions" style={{ marginBottom: "0.55rem" }}>
                <span className="pill">learn/flowlab/gcd.v · {lineCount} righe</span>
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
                onChange={(e) => onRtlChange(e.target.value)}
                aria-label="Editor RTL Verilog"
                rows={24}
              />
            </div>
          ) : (
            <div className="flowlab-params flowlab-params-rich">
              <label>
                SDC (periodo clock)
                <select
                  value={params.sdcPreset}
                  onChange={(e) =>
                    updateParam(
                      "sdcPreset",
                      e.target.value as FlowlabParams["sdcPreset"],
                    )
                  }
                >
                  <option value="default">default · 0.46 ns</option>
                  <option value="relaxed">relaxed · 2.0 ns</option>
                  <option value="tight">tight · 0.25 ns</option>
                </select>
              </label>
              <label>
                ABC area / delay
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
              <label>
                Core utilization · {params.coreUtilization}%
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
              <label>
                Place density addon · {params.placeDensityAddon.toFixed(2)}
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
              <label>
                TNS end percent · {params.tnsEndPercent}%
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
              <div className="flowlab-param-summary muted">
                Override make:{" "}
                <code>
                  FLOW_VARIANT=flowlab CORE_UTILIZATION={params.coreUtilization}{" "}
                  SDC={params.sdcPreset} ABC_AREA={params.abcArea}
                </code>
              </div>
            </div>
          )}

          {offerNext && nextPhase && ok && (
            <div className="flowlab-next">
              <div>
                <strong>{phase.label} ok</strong>
                <p className="muted" style={{ margin: 0 }}>
                  Continua con {nextPhase.title}
                </p>
              </div>
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  setPhaseId(nextPhase.id);
                  setOfferNext(false);
                  setOk(null);
                  setLog("");
                }}
              >
                Vai a {nextPhase.label.replace(/^\d+\s·\s/, "")} →
              </button>
            </div>
          )}
        </section>

        <section className="panel flowlab-side">
          <div className="flowlab-side-tabs" role="tablist">
            {(
              [
                ["log", "Log live"],
                ["artifacts", "Artefatti"],
                ["inspect", "Ispeziona"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={rightTab === id}
                className={clsx("chip", rightTab === id && "chip-active")}
                onClick={() => setRightTab(id)}
              >
                {label}
              </button>
            ))}
          </div>

          {rightTab === "log" && (
            <div className="flowlab-log-pane">
              <div className="lesson-actions" style={{ marginBottom: "0.45rem" }}>
                {ok !== null && (
                  <span className={clsx("pill", ok ? "ok" : "bad")}>
                    {ok ? "ok" : "errore"}
                  </span>
                )}
                {running && <span className="pill">{formatMs(elapsed)}</span>}
                <button type="button" className="btn-ghost btn-tiny" onClick={exportLog}>
                  Export log
                </button>
              </div>
              {blockMsg && <p className="block-banner">{blockMsg}</p>}
              {command && (
                <p className="muted" style={{ fontSize: "0.78rem" }}>
                  <code>{command}</code>
                </p>
              )}
              <pre className="run-log" ref={logRef} aria-live="polite">
                {log ||
                  (running
                    ? "Streaming log…"
                    : "Premi Esegui: qui vedrai il log live della fase.")}
              </pre>
            </div>
          )}

          {rightTab === "artifacts" && (
            <div>
              {phase.id === "rtl" ? (
                <p className="muted">
                  Dopo la sim, il VCD è in <code>learn/sim/gcd/</code>. Gli artefatti
                  PD compaiono dalle fasi successive.
                </p>
              ) : (
                <>
                  <div className="lesson-actions" style={{ marginBottom: "0.6rem" }}>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={guiBusy || running}
                      onClick={() => void openGui()}
                    >
                      {guiBusy ? "Apro…" : "Apri GUI Desktop"}
                    </button>
                  </div>
                  <ResultsPanel
                    stage={resultsStage}
                    variant="flowlab"
                    refreshKey={refreshKey}
                  />
                </>
              )}
            </div>
          )}

          {rightTab === "inspect" && (
            <div>
              {phase.id === "rtl" ? (
                <p className="muted">
                  L’ispezione ODB/STA/Yosys è disponibile dalla sintesi in poi.
                </p>
              ) : (
                <InspectPanel
                  stage={resultsStage}
                  variant="flowlab"
                  refreshKey={refreshKey}
                />
              )}
            </div>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title={`Confermi ${phase.label}?`}
        body={`La fase ${phase.action} può richiedere diversi minuti. Un solo job alla volta.`}
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

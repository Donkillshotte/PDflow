"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import clsx from "clsx";
import {
  CloudUpload,
  Keyboard,
  PanelRightClose,
  PanelRightOpen,
  Play,
  RotateCcw,
  Save,
  Square,
} from "lucide-react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ResultsPanel } from "@/components/ResultsPanel";
import { InspectPanel } from "@/components/InspectPanel";
import { useToast } from "@/components/ToastProvider";
import { FlowLabMetricsBar } from "@/components/flowlab/FlowLabMetricsBar";
import { FlowLabParamStudio } from "@/components/flowlab/FlowLabParamStudio";
import { FlowLabPhaseHistory } from "@/components/flowlab/FlowLabPhaseHistory";
import { FlowLabPhaseVisual } from "@/components/flowlab/FlowLabPhaseVisual";
import { FlowLabPowerChain } from "@/components/flowlab/FlowLabPowerChain";
import { FlowLabPipeline } from "@/components/flowlab/FlowLabPipeline";
import { FlowLabRtlEditor } from "@/components/flowlab/FlowLabRtlEditor";
import { FlowLabSignoff } from "@/components/flowlab/FlowLabSignoff";
import { FlowLabTerminal } from "@/components/flowlab/FlowLabTerminal";
import { LONG_ACTIONS, PHASE_IDS, PHASES } from "@/components/flowlab/phases";
import type {
  FlowlabParams,
  RightTab,
  StageStatus,
  StreamEvent,
} from "@/components/flowlab/types";
import { PARAM_PRESETS } from "@/components/flowlab/types";

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

function FlowLabSkeleton() {
  return (
    <div className="fl-pro fl-loading" aria-busy="true">
      <div className="fl-skel fl-skel-hero" />
      <div className="fl-skel fl-skel-pipeline" />
      <div className="fl-workbench-grid">
        <div className="fl-skel fl-skel-main" />
        <div className="fl-skel fl-skel-side" />
      </div>
    </div>
  );
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
  const [sideWidth, setSideWidth] = useState(280);
  const [sideCollapsed, setSideCollapsed] = useState(true);
  const [sim, setSim] = useState<{
    vcdExists: boolean;
    logExists: boolean;
    vcdBytes: number;
  }>({ vcdExists: false, logExists: false, vcdBytes: 0 });
  const [phaseHistory, setPhaseHistory] = useState<
    Record<string, { id: string; action: string; status: string; startedAt: string; ms?: number }[]>
  >({});
  const [signoffBusy, setSignoffBusy] = useState<string | null>(null);
  const [pendingSignoff, setPendingSignoff] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);
  const tickRef = useRef<number | null>(null);
  const saveTimer = useRef<number | null>(null);
  const rtlRef = useRef(rtl);
  const paramsRef = useRef(params);
  const urlReady = useRef(false);
  const dragRef = useRef<{ startX: number; startW: number } | null>(null);

  const phase = PHASES.find((p) => p.id === phaseId) ?? PHASES[0];
  const resultsStage =
    phase.id === "rtl"
      ? "synth"
      : phase.id === "pdn"
        ? "pdn"
        : phase.id === "pkg"
          ? "finish"
          : phase.id;
  const doneCount = stages.filter((s) => s.done).length;
  const progressPct = Math.round((doneCount / PHASES.length) * 100);
  const unlocked = phaseUnlocked(phaseId, stages);
  const nextPhase = PHASES[PHASE_IDS.indexOf(phaseId) + 1] ?? null;
  const lineCount = useMemo(() => rtl.split("\n").length, [rtl]);

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
      setSim(data.sim ?? { vcdExists: false, logExists: false, vcdBytes: 0 });
      setPhaseHistory(data.phaseHistory ?? {});
      setDirty(false);
      return data;
    } catch (e) {
      push(e instanceof Error ? e.message : "FlowLab error", "bad");
      return null;
    }
  }, [push]);

  useEffect(() => {
    setLoading(true);
    void load().finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    const q = search.get("phase");
    if (q && PHASE_IDS.includes(q) && q !== phaseId) setPhaseId(q);
    urlReady.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  useEffect(() => {
    if (!urlReady.current) return;
    if (search.get("phase") === phaseId) return;
    router.replace(`/flusso?phase=${phaseId}`, { scroll: false });
  }, [phaseId, router, search]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
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
        if (!quiet) push("Saved", "ok");
        return true;
      } catch (e) {
        push(e instanceof Error ? e.message : "save failed", "bad");
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
    }, 800);
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

  function applyPreset(key: string) {
    const preset = PARAM_PRESETS[key];
    if (!preset) return;
    setParams(preset.params);
    paramsRef.current = preset.params;
    scheduleAutosave(rtlRef.current, preset.params);
    push(`Profile «${preset.label}» applied`, "info");
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
      if (!res.ok) throw new Error(body.error || "reset failed");
      setRtl(body.rtl);
      rtlRef.current = body.rtl;
      setDirty(false);
      push("RTL restored from golden", "info");
    } catch (e) {
      push(e instanceof Error ? e.message : "reset failed", "bad");
    } finally {
      setSaving(false);
    }
  }

  const runAction = useCallback(async (overrideAction?: string) => {
    const action = overrideAction ?? phase.action;
    if (dirty && !overrideAction) {
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
      action,
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
                ? `${action} completed · ${formatMs(ev.ms)}`
                : `${action} failed`,
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
        push(e instanceof Error ? e.message : "run failed", "bad");
        setOk(false);
      }
    } finally {
      setRunning(false);
      setSignoffBusy(null);
      abortRef.current = null;
      if (tickRef.current) {
        window.clearInterval(tickRef.current);
        tickRef.current = null;
      }
    }
  }, [dirty, saveAll, phase, nextPhase, push, load]);

  async function runSignoff(action: string, long: boolean) {
    if (running) return;
    if (long) {
      setPendingSignoff(action);
      setConfirmOpen(true);
      return;
    }
    setSignoffBusy(action);
    await runAction(action);
  }

  const phaseRuns =
    phaseHistory[phase.action] ??
    (phase.id === "finish" ? phaseHistory.klayout_drc : undefined) ??
    [];

  const requestRun = useCallback(() => {
    if (!unlocked) {
      push("Complete the previous phase first", "bad");
      return;
    }
    if (LONG_ACTIONS.has(phase.action)) {
      setConfirmOpen(true);
      return;
    }
    void runAction();
  }, [unlocked, phase.action, push, runAction]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key === "s") {
        e.preventDefault();
        void saveAll();
      }
      if (mod && e.key === "Enter") {
        e.preventDefault();
        requestRun();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [saveAll, requestRun]);

  useEffect(() => {
    if (running) setSideCollapsed(false);
  }, [running]);

  async function cancel() {
    if (jobId) {
      await fetch("/api/run/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId }),
      });
    }
    abortRef.current?.abort();
    push("Run cancelled", "info");
  }

  async function openGui() {
    if (phase.id === "rtl") return;
    setGuiBusy(true);
    try {
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
        push(body.message || "GUI command copied — open Desktop", "info");
      } else {
        push(body.message || "No GUI ready for this phase", "bad");
      }
    } finally {
      setGuiBusy(false);
    }
  }

  function exportLog() {
    const blob = new Blob([log || "(empty)"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `flowlab-${phase.id}-${Date.now()}.log`;
    a.click();
    URL.revokeObjectURL(url);
    push("Log exported", "ok");
  }

  function selectPhase(id: string) {
    setPhaseId(id);
    setOfferNext(false);
    setOk(null);
  }

  function onResizeStart(e: React.PointerEvent) {
    dragRef.current = { startX: e.clientX, startW: sideWidth };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onResizeMove(e: React.PointerEvent) {
    if (!dragRef.current) return;
    const delta = dragRef.current.startX - e.clientX;
    setSideWidth(Math.min(560, Math.max(300, dragRef.current.startW + delta)));
  }

  function onResizeEnd() {
    dragRef.current = null;
  }

  if (loading) return <FlowLabSkeleton />;

  return (
    <div className="fl-pro">
      <header className="fl-hero">
        <div className="fl-hero-copy">
          <p className="fl-eyebrow">OpenROAD Studio · FlowLab</p>
          <h1>From RTL to GDSII, phase by phase</h1>
          <p>
            Interactive workbench with Verilog editor, live ORFS parameters, streaming log
            and artifact inspection. Variante isolata{" "}
            <code>results/nangate45/gcd/flowlab</code>.
          </p>
        </div>
        <div className="fl-hero-stats">
          <div className="fl-progress-ring" style={{ "--pct": progressPct } as React.CSSProperties}>
            <svg viewBox="0 0 36 36" aria-hidden>
              <path
                className="fl-ring-bg"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className="fl-ring-fill"
                strokeDasharray={`${progressPct}, 100`}
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <span>{progressPct}%</span>
          </div>
          <div>
            <strong>{doneCount} / {PHASES.length}</strong>
            <span>phases completed</span>
          </div>
        </div>
      </header>

      <FlowLabPipeline
        phases={PHASES}
        phaseId={phaseId}
        stages={stages}
        running={running}
        onSelect={selectPhase}
      />

      <div className="fl-toolbar">
        <div className="fl-toolbar-left">
          <h2>{phase.title}</h2>
          <p>{phase.help}</p>
        </div>
        <div className="fl-toolbar-right">
          <span className="fl-kbd-hint" title="Shortcuts">
            <Keyboard size={14} aria-hidden />
            <kbd>Ctrl</kbd>+<kbd>S</kbd> · <kbd>Ctrl</kbd>+<kbd>Enter</kbd>
          </span>
          <span className={clsx("fl-sync-pill", dirty ? "dirty" : saving ? "saving" : "ok")}>
            {saving ? (
              <>
                <CloudUpload size={14} className="fl-spin" aria-hidden /> Saving…
              </>
            ) : dirty ? (
              "Local changes"
            ) : (
              <>
                <Save size={14} aria-hidden /> Synced
              </>
            )}
          </span>
          <button
            type="button"
            className={clsx("fl-btn fl-btn-ghost", sideCollapsed && "chip-active")}
            onClick={() => setSideCollapsed((v) => !v)}
            title={sideCollapsed ? "Show console" : "Hide console"}
          >
            {sideCollapsed ? (
              <PanelRightOpen size={16} aria-hidden />
            ) : (
              <PanelRightClose size={16} aria-hidden />
            )}
            {sideCollapsed ? "Console" : "Expand chip"}
          </button>
          <button
            type="button"
            className="fl-btn fl-btn-ghost"
            disabled={saving || running}
            onClick={() => void saveAll()}
          >
            <Save size={16} aria-hidden />
            Save
          </button>
          {running ? (
            <button type="button" className="fl-btn fl-btn-danger" onClick={() => void cancel()}>
              <Square size={16} aria-hidden />
              Stop
            </button>
          ) : (
            <button
              type="button"
              className="fl-btn fl-btn-primary"
              disabled={!unlocked && !stages.find((s) => s.id === phaseId)?.done}
              onClick={requestRun}
            >
              <Play size={16} aria-hidden />
              Run {phase.label}
            </button>
          )}
        </div>
      </div>

      {!unlocked && (
        <div className="fl-lock-banner">
          Phase locked — complete «{PHASES[PHASE_IDS.indexOf(phaseId) - 1]?.label}» to
          unlock.
        </div>
      )}

      <div
        className={clsx(
          "fl-workbench-grid",
          sideCollapsed && "is-collapsed",
          phase.id === "rtl" && "is-rtl",
        )}
        style={{ "--fl-side-w": `${sideWidth}px` } as React.CSSProperties}
      >
        <section className="fl-main-panel">
          {phase.id === "rtl" ? (
            <>
              <FlowLabPhaseVisual
                phaseId={phaseId}
                stage={resultsStage}
                variant="flowlab"
                params={params}
                refreshKey={refreshKey}
                rtlLines={lineCount}
                sim={sim}
                stageDone={Boolean(stages.find((s) => s.id === phaseId)?.done)}
              />
              <div className="fl-editor-shell">
              <div className="fl-editor-toolbar">
                <span>
                  <code>learn/flowlab/gcd.v</code> · {lineCount} lines · Verilog-2001
                </span>
                <button
                  type="button"
                  className="fl-btn fl-btn-ghost fl-btn-sm"
                  disabled={saving || running}
                  onClick={() => void resetGolden()}
                >
                  <RotateCcw size={14} aria-hidden />
                  Restore golden
                </button>
              </div>
              <FlowLabRtlEditor
                value={rtl}
                onChange={onRtlChange}
                readOnly={running}
              />
            </div>
            </>
          ) : phase.id === "pdn" || phase.id === "pkg" ? (
            <div className="fl-phase-workspace">
              <FlowLabPhaseVisual
                phaseId={phaseId}
                stage={resultsStage}
                variant="flowlab"
                params={params}
                refreshKey={refreshKey}
                rtlLines={lineCount}
                sim={sim}
                stageDone={Boolean(stages.find((s) => s.id === phaseId)?.done)}
              />
              <div className="fl-phase-controls">
                <div className="fl-analysis-card">
                  <strong>
                    {phase.id === "pdn" ? "Chip PDN" : "Design package"}
                  </strong>
                  <p>{phase.help}</p>
                  {phase.id === "pkg" && (
                    <p>
                      Theory:{" "}
                      <a href="/pkg">PKG hub</a> ·{" "}
                      <a href="/materiali/reference/spice-power-chain.md">SPICE chain</a> ·{" "}
                      <a href="/materiali/reference/spice-ngspice-primer.md">ngspice</a> ·{" "}
                      <a href="/materiali/sim/spice/README.md">Lab netlist</a>
                    </p>
                  )}
                  {phase.id === "pdn" && (
                    <p>
                      Docs:{" "}
                      <a href="/materiali/reference/spice-chip-mesh.md">Mesh SPICE</a> ·{" "}
                      <a href="/materiali/reference/spice-power-chain.md">Phase chain</a> ·{" "}
                      chip IR post-finish in signoff
                    </p>
                  )}
                </div>
                {phase.id === "pkg" && (
                  <FlowLabSignoff
                    mode="full"
                    disabled={running}
                    busy={signoffBusy}
                    onRun={(a, long) => void runSignoff(a, long)}
                  />
                )}
              </div>
            </div>
          ) : (
            <div className="fl-phase-workspace">
              <FlowLabPhaseVisual
                phaseId={phaseId}
                stage={resultsStage}
                variant="flowlab"
                params={params}
                refreshKey={refreshKey}
                rtlLines={lineCount}
                sim={sim}
                stageDone={Boolean(stages.find((s) => s.id === phaseId)?.done)}
              />
              <div className="fl-phase-controls">
                <FlowLabParamStudio
                  params={params}
                  onChange={updateParam}
                  onApplyPreset={applyPreset}
                />
                {phase.id === "finish" && (
                  <FlowLabSignoff
                    mode="finish"
                    disabled={running}
                    busy={signoffBusy}
                    onRun={(a, long) => void runSignoff(a, long)}
                  />
                )}
              </div>
            </div>
          )}

          {offerNext && nextPhase && ok && (
            <div className="fl-next-banner">
              <div>
                <strong>{phase.label} completed</strong>
                <p>Next step: {nextPhase.title}</p>
              </div>
              <button
                type="button"
                className="fl-btn fl-btn-primary"
                onClick={() => {
                  setPhaseId(nextPhase.id);
                  setOfferNext(false);
                  setOk(null);
                  setLog("");
                }}
              >
                Continua → {nextPhase.label}
              </button>
            </div>
          )}
        </section>

        <div
          className="fl-resize-handle"
          onPointerDown={onResizeStart}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeEnd}
          onPointerCancel={onResizeEnd}
          aria-hidden
        />

        {sideCollapsed && (
          <button
            type="button"
            className="fl-console-dock"
            onClick={() => setSideCollapsed(false)}
          >
            Console
          </button>
        )}

        <aside className="fl-side-panel">
          <div className="fl-side-tabs" role="tablist">
            {(
              [
                ["log", "Console"],
                ["artifacts", "Artifacts"],
                ["inspect", "Inspect"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={rightTab === id}
                className={clsx("fl-tab", rightTab === id && "fl-tab-active")}
                onClick={() => setRightTab(id)}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="fl-side-body">
            {rightTab === "log" && (
              <FlowLabTerminal
                log={log}
                running={running}
                ok={ok}
                elapsed={formatMs(elapsed)}
                command={command}
                blockMsg={blockMsg}
                onExport={exportLog}
                onClear={() => setLog("")}
                logRef={logRef}
              />
            )}

            {rightTab === "artifacts" && (
              <div className="fl-artifacts-pane">
                {phase.id === "rtl" ? (
                  <div className="fl-empty-state">
                    {sim.vcdExists ? (
                      <>
                        <p>Simulation completed — waveform available.</p>
                        <div className="fl-artifacts-actions">
                          <a
                            className="fl-btn fl-btn-primary fl-btn-sm"
                            href="/api/flowlab/download?kind=vcd"
                          >
                            Download VCD ({Math.round(sim.vcdBytes / 1024)} KB)
                          </a>
                          {sim.logExists && (
                            <a
                              className="fl-btn fl-btn-ghost fl-btn-sm"
                              href="/api/flowlab/download?kind=simlog"
                            >
                              sim.log
                            </a>
                          )}
                        </div>
                      </>
                    ) : (
                      <>
                        <p>Run RTL simulation to generate the VCD.</p>
                        <p className="muted">
                          Expected output: <code>learn/sim/gcd/gcd.vcd</code>
                        </p>
                      </>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="fl-artifacts-actions">
                      <button
                        type="button"
                        className="fl-btn fl-btn-primary fl-btn-sm"
                        disabled={guiBusy || running}
                        onClick={() => void openGui()}
                      >
                        {guiBusy ? "Opening…" : "Open GUI Desktop"}
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
              <div className="fl-inspect-pane">
                {phase.id === "rtl" ? (
                  <div className="fl-empty-state">
                    <p>ODB, STA, and Yosys report inspection available from synthesis.</p>
                  </div>
                ) : (
                  <InspectPanel
                    stage={resultsStage}
                    variant="flowlab"
                    refreshKey={refreshKey}
                  />
                )}
              </div>
            )}
          </div>
        </aside>
      </div>

      <FlowLabMetricsBar
        stage={resultsStage}
        variant="flowlab"
        refreshKey={refreshKey}
        visible={phase.id !== "rtl"}
      />
      <FlowLabPowerChain phaseId={phaseId} compact />
      <FlowLabPhaseHistory phaseLabel={phase.label} runs={phaseRuns} />

      <ConfirmDialog
        open={confirmOpen}
        title={
          pendingSignoff
            ? `Confirm ${pendingSignoff}?`
            : `Confirm ${phase.label}?`
        }
        body={
          pendingSignoff
            ? `Signoff ${pendingSignoff} may take several minutes.`
            : `${phase.tool} — est. ${phase.estTime}. One job at a time in the runner.`
        }
        confirmLabel="Run"
        onCancel={() => {
          setConfirmOpen(false);
          setPendingSignoff(null);
        }}
        onConfirm={() => {
          setConfirmOpen(false);
          if (pendingSignoff) {
            const a = pendingSignoff;
            setPendingSignoff(null);
            setSignoffBusy(a);
            void runAction(a);
            return;
          }
          void runAction();
        }}
      />
    </div>
  );
}

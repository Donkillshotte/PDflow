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
import { LeftoverSuiteStrip } from "@/components/LeftoverSuiteStrip";
import { ResultsPanel } from "@/components/ResultsPanel";
import { InspectPanel } from "@/components/InspectPanel";
import { useToast } from "@/components/ToastProvider";
import { FlowLabMetricsBar } from "@/components/flowlab/FlowLabMetricsBar";
import { FlowLabParamStudio } from "@/components/flowlab/FlowLabParamStudio";
import { FlowLabPhaseVisual } from "@/components/flowlab/FlowLabPhaseVisual";
import { FlowLabPowerChain } from "@/components/flowlab/FlowLabPowerChain";
import { FlowLabPipeline } from "@/components/flowlab/FlowLabPipeline";
import { FlowLabRtlEditor } from "@/components/flowlab/FlowLabRtlEditor";
import { FlowLabSignoff } from "@/components/flowlab/FlowLabSignoff";
import { FlowLabTerminal } from "@/components/flowlab/FlowLabTerminal";
import { Asap7FlowWorkspace } from "@/components/Asap7FlowWorkspace";
import { AnalysisRail } from "@/components/AnalysisRail";
import { AnalysisBundleLauncher } from "@/components/AnalysisBundleLauncher";
import { CLOSE_PHASES, LONG_ACTIONS, PHASE_IDS, PHASES } from "@/components/flowlab/phases";
import { FLOWLAB_LOCKED_RECOOK } from "@/lib/actions";
import type {
  FlowlabParams,
  RightTab,
  StageStatus,
  StreamEvent,
} from "@/components/flowlab/types";
import { PARAM_PRESETS } from "@/components/flowlab/types";
import type { VcdWaveform } from "@/lib/vcdWaveform";

function formatMs(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

// The agent keeps the complete log on disk. This bounded copy is only the
// interactive browser buffer; it prevents a noisy native process from
// growing the React tree or the renderer without bound.
const MAX_RENDERED_LOG_BYTES = 512 * 1024;
const MAX_RENDERED_LOG_LINES = 2_000;

function limitRenderedLog(value: string): string {
  let next = value;
  if (next.length > MAX_RENDERED_LOG_BYTES) {
    next = next.slice(-MAX_RENDERED_LOG_BYTES);
  }
  const lines = next.split("\n");
  if (lines.length > MAX_RENDERED_LOG_LINES) {
    next = lines.slice(-MAX_RENDERED_LOG_LINES).join("\n");
  }
  return next;
}

function appendRenderedLog(previous: string, chunk: string): string {
  return limitRenderedLog(previous + chunk);
}

type AgentFlowJob = {
  job_id: string;
  state: string;
  command?: string[];
  log_tail?: string;
  reason?: string | null;
  code?: number | null;
  report?: {
    ok?: boolean;
    status?: string;
    evidence_status?: string;
    requirement_status?: string;
    signoff_status?: string;
    reason?: string | null;
  };
};

type CandidateArtifact = {
  relative_path?: string;
  artifact_id?: string;
  authority?: string;
  mutable?: boolean;
};

const FLOWLAB_CANDIDATE_STAGE_ACTIONS = new Set([
  "synth",
  "floorplan",
  "gridcheck",
  "sta_checkpoint",
  "chip_pdn_ir",
  "dynamic_ir",
  "power_grid_em",
  "place",
  "cts",
  "route",
  "finish",
]);

const FLOWLAB_ANALYSIS_ACTIONS = new Set([
  "gridcheck",
  "sta_checkpoint",
  "chip_pdn_ir",
  "dynamic_ir",
  "power_grid_em",
]);

const FLOWLAB_CANDIDATE_STAGE_ARTIFACTS: Record<string, string[]> = {
  synth: ["1_synth.odb"],
  floorplan: ["2_floorplan.odb"],
  pdn: [".gridcheck_pdn.ok"],
  place: ["3_place.odb"],
  cts: ["4_cts.odb"],
  route: ["5_route.odb"],
  finish: ["6_final.gds"],
};

const FLOWLAB_LAYOUT_STORAGE_KEY = "pdflow:flowlab-layout:v1";

function isCandidateRunId(value: string | null): value is string {
  return Boolean(value && /^[A-Za-z0-9_.-]{8,100}$/.test(value));
}

function artifactBaseName(relativePath: string | undefined) {
  return relativePath?.split("/").pop() ?? "";
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
  const search = useSearchParams();
  if (search.get("platform") === "asap7") {
    return <Asap7FlowWorkspace />;
  }
  return <FlowLabCourse />;
}

function FlowLabCourse() {
  const { push } = useToast();
  const router = useRouter();
  const search = useSearchParams();
  const initialPhase = (() => {
    const q = search.get("phase");
    if (q === "pkg") return "rtl";
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
  const [panelLayoutReady, setPanelLayoutReady] = useState(false);
  const [sim, setSim] = useState<{
    vcdExists: boolean;
    logExists: boolean;
    vcdBytes: number;
  }>({ vcdExists: false, logExists: false, vcdBytes: 0 });
  const [waveform, setWaveform] = useState<VcdWaveform | null>(null);
  const [signoffBusy, setSignoffBusy] = useState<string | null>(null);
  const [pendingSignoff, setPendingSignoff] = useState<string | null>(null);
  const [candidateRunId, setCandidateRunId] = useState<string | null>(() => {
    const value = search.get("run");
    return isCandidateRunId(value) ? value : null;
  });
  const [candidateArtifacts, setCandidateArtifacts] = useState<CandidateArtifact[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  const agentJobRef = useRef<string | null>(null);
  const lastAgentJobIdRef = useRef<string | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);
  const tickRef = useRef<number | null>(null);
  const saveTimer = useRef<number | null>(null);
  const rtlRef = useRef(rtl);
  const paramsRef = useRef(params);
  const urlReady = useRef(false);
  const dragRef = useRef<{ startX: number; startW: number } | null>(null);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(FLOWLAB_LAYOUT_STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as {
          sideWidth?: number;
          sideCollapsed?: boolean;
          rightTab?: RightTab;
        };
        if (typeof saved.sideWidth === "number" && Number.isFinite(saved.sideWidth)) {
          setSideWidth(Math.min(560, Math.max(280, saved.sideWidth)));
        }
        if (typeof saved.sideCollapsed === "boolean") setSideCollapsed(saved.sideCollapsed);
        if (
          saved.rightTab === "log" ||
          saved.rightTab === "artifacts" ||
          saved.rightTab === "inspect" ||
          saved.rightTab === "checks" ||
          saved.rightTab === "settings" ||
          saved.rightTab === "signoff"
        ) {
          setRightTab(saved.rightTab);
        }
      }
    } catch {
      // A corrupt preference must never prevent FlowLab from opening.
    }
    setPanelLayoutReady(true);
  }, []);

  useEffect(() => {
    if (!panelLayoutReady) return;
    try {
      window.localStorage.setItem(
        FLOWLAB_LAYOUT_STORAGE_KEY,
        JSON.stringify({ sideWidth, sideCollapsed, rightTab }),
      );
    } catch {
      // Layout persistence is optional and must not affect the active run.
    }
  }, [panelLayoutReady, rightTab, sideCollapsed, sideWidth]);

  const phase = PHASES.find((p) => p.id === phaseId) ?? PHASES[0];
  useEffect(() => {
    if (phase.id !== "finish" && rightTab === "signoff") {
      setRightTab("artifacts");
    }
  }, [phase.id, rightTab]);

  const resultsStage =
    phase.id === "rtl" ? "synth" : phase.id === "pdn" ? "pdn" : phase.id;
  const candidateActive = Boolean(candidateRunId);
  const candidateArtifactNames = useMemo(
    () => new Set(candidateArtifacts.map((item) => artifactBaseName(item.relative_path))),
    [candidateArtifacts],
  );
  const visibleStages = useMemo(() => {
    if (!candidateActive) return stages;
    return stages.map((stage) => {
      if (stage.id === "rtl") return stage;
      const expected = FLOWLAB_CANDIDATE_STAGE_ARTIFACTS[stage.id] ?? [];
      const done = expected.some((name) => candidateArtifactNames.has(name));
      return {
        ...stage,
        done,
        ready: true,
        primary: expected[0] ?? stage.primary,
      };
    });
  }, [candidateActive, candidateArtifactNames, stages]);
  const closeStages = visibleStages;
  const doneCount = closeStages.filter((s) => s.done).length;
  const progressPct = Math.round((doneCount / CLOSE_PHASES.length) * 100);
  const unlocked = phaseUnlocked(phaseId, visibleStages);
  const canonicalFinishDone = Boolean(stages.find((s) => s.id === "finish")?.done);
  const recookBlocked =
    canonicalFinishDone && !candidateActive && FLOWLAB_LOCKED_RECOOK.has(phase.action);
  const candidateActionBlocked =
    candidateActive && !FLOWLAB_CANDIDATE_STAGE_ACTIONS.has(phase.action);
  const nextPhase =
    CLOSE_PHASES[CLOSE_PHASES.findIndex((p) => p.id === phaseId) + 1] ?? null;
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
      setWaveform(data.sim?.waveform ?? null);
      setDirty(false);
      return data;
    } catch (e) {
      push(e instanceof Error ? e.message : "FlowLab error", "bad");
      return null;
    }
  }, [push]);

  const loadCandidateArtifacts = useCallback(async () => {
    if (!candidateRunId) {
      setCandidateArtifacts([]);
      return;
    }
    try {
      const res = await fetch(
        `/api/artifacts?run_id=${encodeURIComponent(candidateRunId)}&authority=candidate&limit=2000`,
        { cache: "no-store" },
      );
      if (!res.ok) {
        setCandidateArtifacts([]);
        return;
      }
      const data = (await res.json()) as { artifacts?: CandidateArtifact[] };
      setCandidateArtifacts(data.artifacts ?? []);
    } catch {
      setCandidateArtifacts([]);
    }
  }, [candidateRunId]);

  useEffect(() => {
    setLoading(true);
    void load().finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    void loadCandidateArtifacts();
  }, [loadCandidateArtifacts, refreshKey]);

  useEffect(() => {
    if (search.get("phase") === "pkg") {
      router.replace("/pkg");
      return;
    }
    const q = search.get("phase");
    if (q && PHASE_IDS.includes(q) && q !== "pkg" && q !== phaseId) setPhaseId(q);
    const run = search.get("run");
    if (isCandidateRunId(run) && run !== candidateRunId) setCandidateRunId(run);
    if ((!run || !isCandidateRunId(run)) && candidateRunId) setCandidateRunId(null);
    urlReady.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  useEffect(() => {
    if (!urlReady.current) return;
    if (search.get("phase") === "pkg") return;
    if (
      search.get("phase") === phaseId &&
      search.get("run") === (candidateRunId ?? null)
    ) {
      return;
    }
    const hash = typeof window !== "undefined" ? window.location.hash : "";
    const focus = search.get("focus");
    const qs = new URLSearchParams();
    qs.set("phase", phaseId);
    if (candidateRunId) qs.set("run", candidateRunId);
    if (focus) qs.set("focus", focus);
    router.replace(`/flow?${qs.toString()}${hash}`, { scroll: false });
  }, [candidateRunId, phaseId, router, search]);

  useEffect(() => {
    if (loading || typeof window === "undefined") return;
    const focus = search.get("focus") || window.location.hash.replace(/^#/, "");
    if (!focus) return;
    if (focus === "signoff" && phase.id === "finish") {
      setSideCollapsed(false);
      setRightTab("signoff");
    }
    const t = window.setTimeout(() => {
      const el = document.getElementById(focus);
      el?.closest("details")?.setAttribute("open", "");
      el?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
    return () => window.clearTimeout(t);
  }, [loading, phase.id, phaseId, search]);

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

  function activateCandidate(runId: string, targetPhase = phaseId) {
    setCandidateRunId(runId);
    setCandidateArtifacts([]);
    setPhaseId(targetPhase);
    setOfferNext(false);
    setOk(null);
    router.replace(
      `/flow?phase=${encodeURIComponent(targetPhase)}&run=${encodeURIComponent(runId)}`,
      { scroll: false },
    );
  }

  async function startCandidateRun() {
    if (running) return;
    if (dirty) {
      const saved = await saveAll(rtlRef.current, paramsRef.current, true);
      if (!saved) return;
    }
    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ surface: "flow", profile: "flowlab-candidate" }),
      });
      const body = (await response.json().catch(() => ({}))) as {
        run?: { run_id?: string };
        error?: string;
      };
      if (!response.ok || !body.run?.run_id) {
        throw new Error(body.error || "Candidate run could not be created");
      }
      const runId = body.run.run_id;
      activateCandidate(runId, "synth");
      setLog("");
      push(
        "Isolated candidate ready — Synth can recook without touching the finish.",
        "ok",
      );
    } catch (error) {
      push(error instanceof Error ? error.message : "Candidate run failed", "bad");
    }
  }

  function exitCandidate() {
    if (running) return;
    setCandidateRunId(null);
    setCandidateArtifacts([]);
    const qs = new URLSearchParams();
    qs.set("phase", phaseId);
    router.replace(`/flow?${qs.toString()}`, { scroll: false });
    push("Returned to protected FlowLab finish", "info");
  }

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
    if (canonicalFinishDone && !candidateActive) return;
    setParams((p) => {
      const next = { ...p, [key]: value };
      paramsRef.current = next;
      scheduleAutosave(rtlRef.current, next);
      return next;
    });
  }

  function applyPreset(key: string) {
    if (canonicalFinishDone && !candidateActive) return;
    const preset = PARAM_PRESETS[key];
    if (!preset) return;
    setParams(preset.params);
    paramsRef.current = preset.params;
    scheduleAutosave(rtlRef.current, preset.params);
    push(`Profile "${preset.label}" applied`, "info");
  }

  async function resetUpstreamRtl() {
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
      push("RTL restored from upstream source", "info");
    } catch (e) {
      push(e instanceof Error ? e.message : "reset failed", "bad");
    } finally {
      setSaving(false);
    }
  }

  const runAction = useCallback(
    async (
      overrideAction?: string,
      analysisStage?: string,
      analysisParameters?: Record<string, unknown>,
    ) => {
    const action = overrideAction ?? phase.action;
    if (candidateActive && !FLOWLAB_CANDIDATE_STAGE_ACTIONS.has(action)) {
      const message =
        "Candidate runs support FlowLab stages only. Exit the candidate to use Product signoff.";
      setBlockMsg(message);
      setOk(false);
      push(message, "bad");
      return;
    }
    if (dirty && !overrideAction) {
      const saved = await saveAll(rtlRef.current, paramsRef.current, true);
      if (!saved) return;
    }
    setRunning(true);
    setOk(null);
    setLog("");
    setBlockMsg(null);
    setJobId(null);
    agentJobRef.current = null;
    lastAgentJobIdRef.current = null;
    setOfferNext(false);
    setElapsed(0);
    setRightTab("log");
    const started = Date.now();
    if (tickRef.current) window.clearInterval(tickRef.current);
    tickRef.current = window.setInterval(() => {
      setElapsed(Date.now() - started);
    }, 200);

    const p = paramsRef.current;
    const isAnalysisAction = FLOWLAB_ANALYSIS_ACTIONS.has(action);
    const requestParameters: Record<string, unknown> = isAnalysisAction
      ? {
          checkpoint: analysisStage ?? resultsStage,
          ...(analysisParameters ?? {}),
        }
      : {
          coreUtilization: p.coreUtilization,
          placeDensityAddon: p.placeDensityAddon,
          abcArea: p.abcArea,
          sdcPreset: p.sdcPreset,
          tnsEndPercent: p.tnsEndPercent,
        };
    const q = new URLSearchParams({ action, mode: "flowlab" });
    for (const [key, value] of Object.entries(requestParameters)) {
      if (value !== undefined && value !== null) q.set(key, String(value));
    }
    const ac = new AbortController();
    abortRef.current = ac;

    try {
      // The local agent owns the desktop execution path. The legacy SSE route
      // remains a browser/dev fallback while the agent is unavailable.
      const runSurface = [
        "sta_signoff",
        "sta_ir_aware",
        "drc_signoff",
        "klayout_lvs",
        "power_signoff",
        "signoff_all",
      ].includes(action)
        ? "product"
        : "flow";
      let runId: string | null = candidateActive ? candidateRunId : null;
      let runResponse: Response | null = null;
      if (!runId) {
        runResponse = await fetch("/api/runs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ surface: runSurface, profile: "flowlab-live" }),
          signal: ac.signal,
        });
        if (runResponse.ok) {
          const runBody = (await runResponse.json()) as {
            run?: { run_id?: string };
          };
          runId = runBody.run?.run_id ?? null;
          if (!runId) throw new Error("Local agent did not return a run_id");
        }
      }
      if (runId && (!runResponse || runResponse.ok)) {
        const agentResponse = await fetch("/api/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action,
            operation: "action",
            variant: "flowlab",
            mode: "view",
            run_id: runId,
            candidate_run_id: candidateActive ? candidateRunId : undefined,
            parameters: requestParameters,
          }),
          signal: ac.signal,
        });
        if (agentResponse.status !== 503) {
          const body = (await agentResponse.json().catch(() => ({}))) as AgentFlowJob & {
            error?: string;
          };
          if (!agentResponse.ok) {
            const message = body.error || `Local agent rejected ${action}`;
            setBlockMsg(message);
            setOk(false);
            push(message, "bad");
            return;
          }
          let job = body;
          agentJobRef.current = job.job_id;
          lastAgentJobIdRef.current = job.job_id;
          setJobId(job.job_id);
          setCommand((job.command || []).join(" "));
          setLog(
            limitRenderedLog(
              "$ " +
                (job.command || []).join(" ") +
                "\n\n" +
                (job.log_tail || ""),
            ),
          );
          while (job.state === "QUEUED" || job.state === "RUNNING") {
            await new Promise((resolve) => window.setTimeout(resolve, 450));
            const jobResponse = await fetch(
              "/api/jobs/" + encodeURIComponent(job.job_id),
              { signal: ac.signal },
            );
            if (!jobResponse.ok) throw new Error("Local agent status unavailable");
            job = (await jobResponse.json()) as AgentFlowJob;
            setLog(
              limitRenderedLog(
                "$ " +
                  (job.command || []).join(" ") +
                  "\n\n" +
                  (job.log_tail || ""),
              ),
            );
          }
          const reportStatus = String(job.report?.status || "").toUpperCase();
          const evidenceComplete =
            job.state === "COMPLETED" &&
            ["PASS", "FAIL", "WARN", "PARTIAL", "PROXY"].includes(reportStatus) &&
            job.report?.evidence_status !== "GAP";
          const finalOk = job.state === "COMPLETED" && job.report?.ok === true;
          const reason = job.reason || job.report?.reason || null;
          setOk(finalOk);
          if (reason && !finalOk && !evidenceComplete) setBlockMsg(reason);
          setLog((current) =>
            appendRenderedLog(
              current,
              "\n—— done · " +
                job.state +
                " · exit " +
                (job.code ?? "?") +
                " ——\n",
            ),
          );
          push(
            finalOk
              ? `${action} completed · local agent`
              : evidenceComplete
                ? `${action} completed · ${reportStatus} evidence (not Product signoff)`
                : reason || `${action} ${job.state.toLowerCase()}`,
            finalOk ? "ok" : evidenceComplete ? "info" : "bad",
          );
          if (finalOk || evidenceComplete) {
            setRefreshKey((key) => key + 1);
            if (finalOk && action === phase.action) setOfferNext(true);
            if (FLOWLAB_ANALYSIS_ACTIONS.has(action)) {
              setRightTab("checks");
            } else if (phase.id !== "rtl") {
              setRightTab("artifacts");
            }
            await load();
          }
          return;
        }
        if (candidateActive) {
          const message =
            "Candidate execution requires the authenticated PDflow local agent.";
          setBlockMsg(message);
          setOk(false);
          push(message, "bad");
          return;
        }
      } else if (candidateActive) {
        const message =
          "Candidate execution requires the authenticated PDflow local agent.";
        setBlockMsg(message);
        setOk(false);
        push(message, "bad");
        return;
      } else if (runResponse && runResponse.status !== 503) {
        const body = (await runResponse.json().catch(() => ({}))) as { error?: string };
        throw new Error(body.error || `HTTP ${runResponse.status}`);
      }

      agentJobRef.current = null;
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
            setLog((L) => appendRenderedLog(L, ev.chunk));
          } else if (ev.type === "blocked") {
            setBlockMsg(ev.message);
            setOk(false);
            push(ev.message, "bad");
          } else if (ev.type === "error") {
            setLog((L) => appendRenderedLog(L, `\n[error] ${ev.message}\n`));
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
              if (action === phase.action) setOfferNext(true);
              if (FLOWLAB_ANALYSIS_ACTIONS.has(action)) {
                setRightTab("checks");
              } else if (phase.id !== "rtl") {
                setRightTab("artifacts");
              }
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
      agentJobRef.current = null;
      abortRef.current = null;
      if (tickRef.current) {
        window.clearInterval(tickRef.current);
        tickRef.current = null;
      }
    }
    }, [candidateActive, candidateRunId, dirty, load, phase, push, resultsStage, saveAll]);

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

  const requestRun = useCallback(() => {
    if (candidateActionBlocked) {
      push(
        "Candidate runs support FlowLab stages only. Exit the candidate to use Product signoff.",
        "bad",
      );
      return;
    }
    if (!unlocked) {
      push("Complete the previous phase first", "bad");
      return;
    }
    if (recookBlocked) {
      push(
        "flowlab finish is locked. Recook would overwrite gcd/flowlab.",
        "bad",
      );
      return;
    }
    if (LONG_ACTIONS.has(phase.action)) {
      setConfirmOpen(true);
      return;
    }
    void runAction();
  }, [candidateActionBlocked, unlocked, recookBlocked, phase.action, push, runAction]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      const target = e.target as HTMLElement | null;
      if (
        target?.isContentEditable ||
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT"
      ) {
        return;
      }
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
    if (jobId && agentJobRef.current === jobId) {
      await fetch("/api/jobs/" + encodeURIComponent(jobId) + "/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      }).catch(() => undefined);
    } else if (jobId) {
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
                  ? "2_4_floorplan_pdn.odb"
                  : resultsStage === "place"
                    ? "3_5_place_dp.odb"
                    : resultsStage === "cts"
                      ? "4_cts.odb"
                      : "5_2_route.odb",
          variant: "flowlab",
          run_id: candidateRunId ?? undefined,
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
    } catch (e) {
      push(e instanceof Error ? e.message : "GUI could not be opened", "bad");
    } finally {
      setGuiBusy(false);
    }
  }

  function exportLog() {
    const agentJobId = lastAgentJobIdRef.current;
    if (agentJobId) {
      const anchor = document.createElement("a");
      anchor.href = "/api/jobs/" + encodeURIComponent(agentJobId) + "/log";
      anchor.download = `flowlab-${phase.id}-${agentJobId.slice(-12)}.log`;
      anchor.rel = "noopener";
      anchor.click();
      push("Complete agent log download started", "ok");
      return;
    }
    const blob = new Blob([log || "(empty)"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `flowlab-${phase.id}-${Date.now()}.log`;
    a.click();
    URL.revokeObjectURL(url);
    push("Log exported", "ok");
  }

  function replacePhaseInUrl(id: string) {
    const qs = new URLSearchParams(
      typeof window !== "undefined" ? window.location.search : search.toString(),
    );
    qs.set("phase", id);
    if (candidateRunId) qs.set("run", candidateRunId);
    else qs.delete("run");
    const hash = typeof window !== "undefined" ? window.location.hash : "";
    router.replace(`/flow?${qs.toString()}${hash}`, { scroll: false });
  }

  function selectPhase(id: string) {
    setPhaseId(id);
    setOfferNext(false);
    setOk(null);
    replacePhaseInUrl(id);
  }

  function onResizeStart(e: React.PointerEvent) {
    dragRef.current = { startX: e.clientX, startW: sideWidth };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  function setPanelWidth(next: number) {
    setSideWidth(Math.min(560, Math.max(280, next)));
  }

  function onResizeMove(e: React.PointerEvent) {
    if (!dragRef.current) return;
    const delta = dragRef.current.startX - e.clientX;
    setPanelWidth(dragRef.current.startW + delta);
  }

  function onResizeEnd() {
    dragRef.current = null;
  }

  const sideTabs: Array<[RightTab, string]> = [
    ["log", "Console"],
    ["artifacts", "Artifacts"],
    ["inspect", "Inspect"],
    ["checks", "Checks"],
    ["settings", "Settings"],
  ];
  if (phase.id === "finish") sideTabs.push(["signoff", "Signoff"]);

  if (loading) return <FlowLabSkeleton />;

  return (
    <div className="fl-pro">
      <header className="fl-hero">
        <div className="fl-hero-copy">
          <p className="fl-eyebrow">OpenROAD Studio · FlowLab</p>
          <h1>RTL → finish → signoff_all</h1>
          <p>
            Isolated GCD at <code>results/nangate45/gcd/flowlab</code>.
            Signoff is STA → DRC → LVS → power. ECO apply writes{" "}
            <code>eco_scratch</code> and still requires{" "}
            <code>signoff_all</code>. PKG is System PDN on{" "}
            <a href="/pkg">/pkg</a>, not a ninth signoff pillar. DSE proposes knobs.
            Leftover stays named on finish.
          </p>
          <LeftoverSuiteStrip compact href="/flow?phase=finish#signoff" />
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
            <strong>{doneCount} / {CLOSE_PHASES.length}</strong>
            <span>RTL → finish · open items stay listed on signoff</span>
          </div>
        </div>
      </header>

      <FlowLabPipeline
        phases={CLOSE_PHASES}
        phaseId={phaseId}
        stages={visibleStages}
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
              disabled={
                recookBlocked ||
                candidateActionBlocked ||
                (!unlocked && !visibleStages.find((s) => s.id === phaseId)?.done)
              }
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
          Phase locked — complete {PHASES[PHASE_IDS.indexOf(phaseId) - 1]?.label} to
          unlock.
        </div>
      )}
      {recookBlocked && (
        <div className="fl-lock-banner">
          <div>
            <strong>Canonical FlowLab finish is read-only.</strong> This ORFS recook
            would overwrite <code>gcd/flowlab</code>.
          </div>
          <button
            type="button"
            className="fl-btn fl-btn-primary fl-btn-sm"
            disabled={running || saving}
            onClick={() => void startCandidateRun()}
          >
            Start isolated candidate recook
          </button>
        </div>
      )}
      {candidateActive && (
        <div className="fl-lock-banner fl-candidate-banner">
          <div>
            <strong>Candidate workspace active.</strong> Run stages write only to{" "}
            <code>.pdflow/runs/{candidateRunId}/candidate/orfs</code>; the canonical
            finish is unchanged.
          </div>
          <button
            type="button"
            className="fl-btn fl-btn-ghost fl-btn-sm"
            disabled={running || saving}
            onClick={exitCandidate}
          >
            Exit candidate
          </button>
        </div>
      )}

      <div
        className={clsx(
          "fl-workbench-grid",
          sideCollapsed && "is-collapsed",
          phase.id === "rtl" && "is-rtl",
          phase.id === "finish" && "is-finish",
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
                waveform={waveform}
                stageDone={Boolean(visibleStages.find((s) => s.id === phaseId)?.done)}
                runId={candidateRunId}
                onCandidateCreated={activateCandidate}
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
                  onClick={() => void resetUpstreamRtl()}
                >
                  <RotateCcw size={14} aria-hidden />
                  Restore upstream RTL
                </button>
              </div>
              <FlowLabRtlEditor
                value={rtl}
                onChange={onRtlChange}
                readOnly={running}
              />
            </div>
            </>
          ) : phase.id === "pdn" ? (
            <div className="fl-phase-workspace">
              <FlowLabPhaseVisual
                phaseId={phaseId}
                stage={resultsStage}
                variant="flowlab"
                params={params}
                refreshKey={refreshKey}
                rtlLines={lineCount}
                sim={sim}
                waveform={waveform}
                stageDone={Boolean(visibleStages.find((s) => s.id === phaseId)?.done)}
                runId={candidateRunId}
                onCandidateCreated={activateCandidate}
              />
              <div className="fl-phase-controls">
                <div className="fl-analysis-card">
                  <strong>Chip PDN</strong>
                  <p>{phase.help}</p>
                  <p>
                    Docs:{" "}
                    <a href="/materials/reference/spice-chip-mesh.md">Mesh SPICE</a> ·{" "}
                    <a href="/materials/reference/spice-power-chain.md">Phase chain</a> ·{" "}
                    chip IR post-finish in signoff. System PDN is on{" "}
                    <a href="/pkg">/pkg</a>.
                  </p>
                </div>
              </div>
            </div>
          ) : phase.id === "finish" ? (
            <div className="fl-phase-workspace">
              <FlowLabPhaseVisual
                phaseId={phaseId}
                stage={resultsStage}
                variant="flowlab"
                params={params}
                refreshKey={refreshKey}
                rtlLines={lineCount}
                sim={sim}
                waveform={waveform}
                stageDone={Boolean(visibleStages.find((s) => s.id === phaseId)?.done)}
                runId={candidateRunId}
                onCandidateCreated={activateCandidate}
              />
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
                waveform={waveform}
                stageDone={Boolean(visibleStages.find((s) => s.id === phaseId)?.done)}
                runId={candidateRunId}
                onCandidateCreated={activateCandidate}
              />
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
                  selectPhase(nextPhase.id);
                  setOfferNext(false);
                  setOk(null);
                  setLog("");
                }}
              >
                Continue → {nextPhase.label}
              </button>
            </div>
          )}
          {offerNext && !nextPhase && phase.id === "finish" && ok && (
            <div className="fl-next-banner">
              <div>
                <strong>Finish completed</strong>
                <p>
                  Four-pillar close stays on this page. Leftover stays named.
                  System PDN / Phase 2 is on /pkg.
                </p>
              </div>
              <a className="fl-btn fl-btn-primary" href="/pkg">
                Open PKG
              </a>
            </div>
          )}
        </section>

        <div
          className="fl-resize-handle"
          onPointerDown={onResizeStart}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeEnd}
          onPointerCancel={onResizeEnd}
          role="separator"
          tabIndex={0}
          aria-label="Resize runtime panel"
          aria-orientation="vertical"
          aria-valuemin={280}
          aria-valuemax={560}
          aria-valuenow={sideWidth}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") {
              event.preventDefault();
              setPanelWidth(sideWidth + 24);
            } else if (event.key === "ArrowRight") {
              event.preventDefault();
              setPanelWidth(sideWidth - 24);
            } else if (event.key === "Home") {
              event.preventDefault();
              setPanelWidth(280);
            } else if (event.key === "End") {
              event.preventDefault();
              setPanelWidth(560);
            }
          }}
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
            {sideTabs.map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                id={`flowlab-tab-${id}`}
                aria-controls="flowlab-side-panel"
                aria-selected={rightTab === id}
                tabIndex={rightTab === id ? 0 : -1}
                className={clsx("fl-tab", rightTab === id && "fl-tab-active")}
                onClick={() => setRightTab(id)}
              >
                {label}
              </button>
            ))}
          </div>

          <div
            id="flowlab-side-panel"
            className="fl-side-body"
            role="tabpanel"
            aria-labelledby={`flowlab-tab-${rightTab}`}
            tabIndex={0}
          >
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
                      runId={candidateRunId}
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
                    runId={candidateRunId}
                  />
                )}
              </div>
            )}

            {rightTab === "checks" && (
              <>
                <AnalysisBundleLauncher
                  stage={resultsStage}
                  variant="flowlab"
                  runId={candidateRunId}
                  onQueued={() => setRefreshKey((key) => key + 1)}
                />
                <AnalysisRail
                  stage={resultsStage}
                  variant="flowlab"
                  runId={candidateRunId}
                  refreshKey={refreshKey}
                  onRunAction={(action, check, parameters) =>
                    void runAction(action, check.stage, parameters)
                  }
                />
              </>
            )}

            {rightTab === "settings" && (
              <div className="fl-settings-pane">
                <FlowLabParamStudio
                  params={params}
                  locked={canonicalFinishDone && !candidateActive}
                  onChange={updateParam}
                  onApplyPreset={applyPreset}
                />
              </div>
            )}

            {rightTab === "signoff" && phase.id === "finish" && (
              <div className="fl-signoff-pane">
                <FlowLabSignoff
                  mode="finish"
                  disabled={running || candidateActive}
                  busy={signoffBusy}
                  onRun={(a, long) => void runSignoff(a, long)}
                />
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
        runId={candidateRunId}
      />
      {phaseId !== "finish" && !candidateActive && (
        <FlowLabPowerChain phaseId={phaseId} compact />
      )}
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
          if (recookBlocked) return;
          void runAction();
        }}
      />
    </div>
  );
}

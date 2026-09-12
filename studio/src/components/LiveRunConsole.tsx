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
  | {
      type: "done";
      ok: boolean;
      code: number | null;
      ms: number;
      status?: string;
      state?: string;
      reportStatus?: string | null;
      reason?: string | null;
      terminationCause?: string | null;
    }
  | { type: "error"; message: string }
  | { type: "blocked"; code: string; message: string };

type AgentJob = {
  job_id: string;
  state: string;
  command?: string[];
  log_tail?: string;
  reason?: string;
  report?: {
    ok?: boolean;
    status?: string;
    evidence_status?: string;
    requirement_status?: string;
    signoff_status?: string;
    reason?: string;
    termination_cause?: string;
  };
  code?: number | null;
};

const EVIDENCE_STATUSES = new Set(["PASS", "FAIL", "WARN", "PARTIAL", "PROXY"]);

function statusHasEvidence(
  state: string,
  status?: string | null,
  evidenceStatus?: string | null,
): boolean {
  return (
    state === "COMPLETED" &&
    EVIDENCE_STATUSES.has(String(status || "").toUpperCase()) &&
    String(evidenceStatus || "").toUpperCase() !== "GAP"
  );
}

function hasCompletedEvidence(state: string, report?: AgentJob["report"]): boolean {
  return statusHasEvidence(state, report?.status, report?.evidence_status);
}

const PIPELINE_ACTIONS = [
  { id: "check", label: "Verify toolchain", hint: "openroad · yosys · sta · klayout" },
  { id: "rtl_sim", label: "RTL sim (Icarus)", hint: "GCD + RTL VCD" },
  { id: "gate_sim", label: "Gate sim (Icarus)", hint: "6_final.v + name-join VCD" },
  { id: "status", label: "Course progress", hint: "lessons completed" },
  { id: "synth", label: "Run synth", hint: "~30s" },
  { id: "floorplan", label: "Run floorplan", hint: "die / PDN" },
  { id: "gridcheck", label: "Gridcheck PDN", hint: "check_power_grid" },
  { id: "sta_checkpoint", label: "STA checkpoint", hint: "OpenSTA · WNS/TNS/slack" },
  { id: "place", label: "Run place", hint: "GP → DP" },
  { id: "cts", label: "Run CTS", hint: "minutes · confirm" },
  { id: "route", label: "Run route", hint: "long · confirm" },
  { id: "finish", label: "Run finish", hint: "GDS · confirm" },
] as const;

type ActionItem = { id: string; label: string; hint: string };

const ACTION_GROUPS: { label: string; items: ActionItem[] }[] = [
  { label: "Pipeline", items: [...PIPELINE_ACTIONS] },
  {
    label: "Signoff",
    items: [
      { id: "sta_signoff", label: "STA signoff", hint: "current timing report" },
      { id: "drc_signoff", label: "DRC signoff", hint: "route + GDS DRC" },
      { id: "klayout_lvs", label: "LVS signoff", hint: "GDS vs netlist" },
      { id: "power_signoff", label: "Power signoff", hint: "IR/droop/Zmax" },
      { id: "signoff_all", label: "Full signoff", hint: "STA → DRC → LVS → power" },
    ],
  },
  {
    label: "ECO",
    items: [
      { id: "eco", label: "ECO propose", hint: "Post-finish plan. Apply refused on flowlab." },
      { id: "eco_apply", label: "ECO apply", hint: "Writes eco_scratch only. Never flowlab." },
      { id: "eco_close", label: "ECO close", hint: "signoff_all on eco_scratch. Cannot skip." },
    ],
  },
  {
    label: "Power / IR",
    items: [
      { id: "activity_power", label: "Activity → power", hint: "set_power_activity" },
      { id: "vectorless", label: "Vectorless / dynamic", hint: "Najm + Kouroussis IR" },
      { id: "chip_pdn_ir", label: "Chip IR mesh", hint: "write_pg_spice" },
      { id: "power_grid_em", label: "Power-grid EM", hint: "vyges-em-ir · proxy" },
      { id: "vyges_em_ir", label: "vyges-em-ir", hint: "CG + backward Euler" },
      { id: "dynamic_ir", label: "Dynamic IR I(t)", hint: "DirectLU current_run" },
      { id: "system_pdn", label: "System PDN", hint: "VRM→board→pkg→die" },
      { id: "power_chain", label: "SPICE chain", hint: "activity→IR→system" },
      { id: "export_spice_lab", label: "Export SPICE lab", hint: "sim/spice/" },
    ],
  },
  {
    label: "Lab / probes",
    items: [
      { id: "sta_ir_aware", label: "STA IR-aware", hint: "NLDM × ITerm V" },
      { id: "thermal_signoff", label: "Thermal (HotSpot)", hint: "t_max °C · Phase 2" },
      { id: "pkg_rdl", label: "PKG RDL (dummy)", hint: "sidecar rdl_route" },
      { id: "pkg_signoff", label: "PKG signoff", hint: "bump/RDL/system" },
      { id: "signoff_phase2", label: "Signoff Phase 2", hint: "HotSpot + PKG" },
      { id: "spice_engines", label: "SPICE engines", hint: "ngspice + Xyce N4" },
      { id: "yosys_equiv", label: "Yosys equiv", hint: "RTL ↔ synth" },
      { id: "formal_gcd", label: "Formal SAT", hint: "reset |-> !resp_val" },
      { id: "openrcx_report", label: "OpenRCX SPEF", hint: "6_final.spef" },
      { id: "analytical_pex", label: "Analytical PEX", hint: "Sakurai + FDM + FasterCap BEM" },
      { id: "ccs_char", label: "CCS char", hint: "PTM sidecar, not foundry CCS" },
      { id: "lab_asap7_pdk", label: "ASAP7 layer 1", hint: "public PDK + leftover Xyce · not Calibre" },
      { id: "lab_asap7_flow", label: "ASAP7 RTL → GDS", hint: "native OpenROAD · OpenSTA · Yosys" },
      { id: "lab_asap7_pkg", label: "ASAP7 PKG", hint: "dummy bump + sidecar RDL + compact VRM · not C4" },
      { id: "lab_asap7_chip_pdn", label: "ASAP7 chip PDN", hint: "write_pg_spice mesh + transient · current ASAP7 track" },
      { id: "lvs_deep", label: "Deep LVS", hint: "filtered CDL + well→VDD/VSS" },
      { id: "layout_tools", label: "Magic / Netgen probe", hint: "no FreePDK45 tech" },
      { id: "tool_matrix", label: "Tool matrix", hint: "all OSS checks" },
    ],
  },
];

const STAGE_ACTIONS = ACTION_GROUPS.flatMap((g) => g.items);

function formatMs(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

const MAX_RENDERED_LOG_BYTES = 32 * 1024;
const MAX_RENDERED_LOG_LINES = 2_000;

function limitRenderedLog(value: string): string {
  let next = value.slice(-MAX_RENDERED_LOG_BYTES);
  const lines = next.split("\n");
  if (lines.length > MAX_RENDERED_LOG_LINES) {
    next = lines.slice(-MAX_RENDERED_LOG_LINES).join("\n");
  }
  return next;
}

function appendRenderedLog(previous: string, chunk: string): string {
  return limitRenderedLog(`${previous}${chunk}`);
}

export function LiveRunConsole({
  defaultAction,
  compact,
  agentVariant = "learn",
  allowedActions,
  runParameters,
  requestedRun,
  onFinished,
}: {
  defaultAction?: string;
  compact?: boolean;
  agentVariant?: string;
  allowedActions?: string[];
  runParameters?: Record<string, unknown>;
  requestedRun?: { action: string; token: number; parameters?: Record<string, unknown> } | null;
  onFinished?: (ok: boolean, action: string) => void;
}) {
  const { push } = useToast();
  const [action, setAction] = useState(defaultAction ?? "check");
  const [running, setRunning] = useState(false);
  const [ok, setOk] = useState<boolean | null>(null);
  const [reportStatus, setReportStatus] = useState<string | null>(null);
  const [evidenceComplete, setEvidenceComplete] = useState(false);
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
  const agentJobRef = useRef<string | null>(null);
  const lastAgentJobIdRef = useRef<string | null>(null);
  const lastActionRef = useRef(action);
  const lastRequestedRunRef = useRef<number | null>(null);
  const digest = useMemo(() => (log ? digestOrfsLog(log) : null), [log]);
  const visibleActionGroups = useMemo(() => {
    if (!allowedActions) return ACTION_GROUPS;
    const allowed = new Set(allowedActions);
    return ACTION_GROUPS
      .map((group) => ({ ...group, items: group.items.filter((item) => allowed.has(item.id)) }))
      .filter((group) => group.items.length > 0);
  }, [allowedActions]);

  useEffect(() => {
    if (defaultAction) setAction(defaultAction);
  }, [defaultAction]);

  useEffect(() => {
    if (allowedActions && !allowedActions.includes(action)) {
      setAction(allowedActions[0] ?? "check");
    }
  }, [action, allowedActions]);

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
    const agentJobId = lastAgentJobIdRef.current;
    if (agentJobId) {
      const anchor = document.createElement("a");
      anchor.href = "/api/jobs/" + encodeURIComponent(agentJobId) + "/log";
      anchor.download = `run-${lastActionRef.current}-${agentJobId.slice(-12)}.log`;
      anchor.rel = "noopener";
      anchor.click();
      push("Complete agent log download started", "ok");
      return;
    }
    const blob = new Blob([log || "(empty)"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `run-${lastActionRef.current}-${Date.now()}.log`;
    a.click();
    URL.revokeObjectURL(url);
    push("Log exported", "ok");
  }

  async function cancel() {
    if (agentJobRef.current) {
      await fetch(
        "/api/jobs/" + encodeURIComponent(agentJobRef.current) + "/cancel",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        },
      ).catch(() => undefined);
    } else if (jobId) {
      await fetch("/api/run/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId }),
      }).catch(() => undefined);
    }
    abortRef.current?.abort();
    push("Job cancelled", "info");
  }

  function requestRun(a = action, parameters?: Record<string, unknown>) {
    if (running) return;
    if (isLongAction(a)) {
      setPendingAction(a);
      setConfirmOpen(true);
      return;
    }
    void run(a, parameters);
  }

  useEffect(() => {
    if (!requestedRun || lastRequestedRunRef.current === requestedRun.token) return;
    lastRequestedRunRef.current = requestedRun.token;
    if (allowedActions && !allowedActions.includes(requestedRun.action)) {
      push("This operation is not enabled for the selected lab profile", "bad");
      return;
    }
    setAction(requestedRun.action);
    requestRun(requestedRun.action, requestedRun.parameters);
    // The token makes the request edge-triggered. The effect may be evaluated
    // again as the console streams output, but it cannot launch a duplicate job.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowedActions, push, requestedRun]);

  async function run(a = action, requestedParameters?: Record<string, unknown>) {
    lastActionRef.current = a;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setRunning(true);
    setOk(null);
    setReportStatus(null);
    setEvidenceComplete(false);
    setLog("");
    setJobId(null);
    agentJobRef.current = null;
    lastAgentJobIdRef.current = null;
    setCommand("");
    setBlockMsg(null);
    setElapsed(0);
    const t0 = Date.now();
    if (tickRef.current) window.clearInterval(tickRef.current);
    tickRef.current = window.setInterval(() => setElapsed(Date.now() - t0), 250);

    try {
      const effectiveParameters = {
        ...(runParameters ?? {}),
        ...(requestedParameters ?? {}),
      };
      const agentStart = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: a,
          operation: "action",
          variant: agentVariant,
          mode: "view",
          ...(Object.keys(effectiveParameters).length > 0
            ? { parameters: effectiveParameters }
            : {}),
        }),
        signal: ac.signal,
      });
      if (agentStart.status !== 503 && agentStart.status !== 400) {
        if (!agentStart.ok) {
          const message = await agentStart.text();
          throw new Error(message || "Local agent rejected the action");
        }
        let job = (await agentStart.json()) as AgentJob;
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
          job = (await jobResponse.json()) as AgentJob;
          setLog(
            limitRenderedLog(
              "$ " +
                (job.command || []).join(" ") +
                "\n\n" +
                (job.log_tail || ""),
            ),
          );
        }
        const finalOk = job.state === "COMPLETED" && job.report?.ok === true;
        const completedEvidence = hasCompletedEvidence(job.state, job.report);
        const finalStatus = String(job.report?.status || "").toUpperCase();
        setReportStatus(finalStatus || null);
        setEvidenceComplete(completedEvidence);
        setOk(finalOk);
        setLog((prev) =>
          appendRenderedLog(
            prev,
            "\n—— done · " +
              job.state +
              " · exit " +
              (job.code ?? "?") +
              " ——\n",
          ),
        );
        setRunning(false);
        if (tickRef.current) window.clearInterval(tickRef.current);
        agentJobRef.current = null;
        push(
          finalOk
            ? a + " completed"
            : completedEvidence
              ? `${a} completed · ${finalStatus} evidence (not Product signoff)`
              : job.reason || a + " " + job.state.toLowerCase(),
          finalOk ? "ok" : completedEvidence ? "info" : "bad",
        );
        onFinished?.(finalOk, a);
        return;
      }
      if (["gridcheck", "sta_checkpoint"].includes(a)) {
        throw new Error("This checkpoint analysis requires the PDflow local agent");
      }
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
        setLog("No SSE body");
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
            setLog((prev) => appendRenderedLog(prev, `$ ${ev.command}\n\n`));
          } else if (ev.type === "stdout" || ev.type === "stderr") {
            setLog((prev) => appendRenderedLog(prev, ev.chunk));
          } else if (ev.type === "error") {
            setLog((prev) => appendRenderedLog(prev, `\n[error] ${ev.message}\n`));
          } else if (ev.type === "blocked") {
            setBlockMsg(ev.message);
            setLog((prev) => appendRenderedLog(prev, `\n[blocked] ${ev.message}\n`));
            push(ev.message, "bad");
          } else if (ev.type === "done") {
            finalOk = ev.ok;
            setOk(ev.ok);
            const streamedStatus = ev.reportStatus
              ? String(ev.reportStatus).toUpperCase()
              : null;
            setReportStatus(streamedStatus);
            setEvidenceComplete(
              statusHasEvidence(ev.state || (ev.ok ? "COMPLETED" : "FAILED"), streamedStatus),
            );
            setLog((prev) =>
              appendRenderedLog(
                prev,
                `\n—— done · ${streamedStatus ?? ev.status ?? (ev.ok ? "ok" : "error")} · exit ${ev.code ?? "?"} · ${formatMs(ev.ms)} ——\n`,
              ),
            );
            push(
              ev.ok
                ? `${a} completed`
                : streamedStatus && statusHasEvidence(ev.state || "COMPLETED", streamedStatus)
                  ? `${a} completed · ${streamedStatus} evidence (not Product signoff)`
                  : `${a} failed (exit ${ev.code})`,
              ev.ok || (streamedStatus && statusHasEvidence(ev.state || "COMPLETED", streamedStatus))
                ? ev.ok ? "ok" : "info"
                : "bad",
            );
          }
        }
      }
      setRunning(false);
      if (tickRef.current) window.clearInterval(tickRef.current);
      onFinished?.(finalOk, a);
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setLog((prev) => appendRenderedLog(prev, "\n[session closed]\n"));
        setOk(false);
      } else {
        setOk(false);
        setLog((prev) =>
          appendRenderedLog(prev, `\n${e instanceof Error ? e.message : String(e)}\n`),
        );
        push("Network error on run", "bad");
      }
      setRunning(false);
      if (tickRef.current) window.clearInterval(tickRef.current);
      onFinished?.(false, a);
    }
  }

  return (
    <div className={clsx("run-console", compact && "run-console-compact")}>
      {!compact && (
        <div className="run-picker">
          <label htmlFor="run-action">Action</label>
          <select
            id="run-action"
            value={action}
            disabled={running}
            onChange={(e) => setAction(e.target.value)}
          >
            {visibleActionGroups.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.items.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <p className="run-picker-hint">
            {STAGE_ACTIONS.find((s) => s.id === action)?.hint ?? ""}
          </p>
        </div>
      )}
      <div className="run-bar">
        {!running ? (
          <>
            <button type="button" className="btn-primary" onClick={() => requestRun()}>
              {compact ? `Launch ${action}` : "Run"}
            </button>
            {ok === false && (
              <button
                type="button"
                className="btn-ghost"
                onClick={() => requestRun(lastActionRef.current)}
              >
                Retry
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
            Cancel
          </button>
        )}
        {running && <span className="pill live">live · {formatMs(elapsed)}</span>}
        {ok === true && <span className="pill ok">PASS</span>}
        {evidenceComplete && ok !== true && (
          <span className="pill info">
            {reportStatus || "EVIDENCE"} · not signoff
          </span>
        )}
        {ok === false && !evidenceComplete && <span className="pill bad">Error</span>}
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
          {log || "Waiting for first output…"}
          {running && <span className="cursor-blink">▍</span>}
        </pre>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title={`Confirm ${pendingAction}?`}
        body="This phase may take several minutes and holds the pipeline lock. Continue only if previous dependencies are complete."
        confirmLabel="Start anyway"
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

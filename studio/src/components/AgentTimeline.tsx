"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import type { JobRecord, ResourceRecord } from "@/lib/pdflowContracts";

function tone(state: string): string {
  if (state === "COMPLETED") return "ok";
  if (state === "RUNNING" || state === "QUEUED") return "live";
  if (state === "GAP" || state === "FAILED" || state === "ORPHANED") return "bad";
  return "warn";
}

function label(job: JobRecord): string {
  return job.action || job.tool_id || job.operation;
}

function formatBytes(value?: number | null): string | null {
  if (!Number.isFinite(value) || !value || value < 0) return null;
  const units = ["B", "KiB", "MiB", "GiB"];
  let n = value;
  let index = 0;
  while (n >= 1024 && index < units.length - 1) {
    n /= 1024;
    index += 1;
  }
  return `${n >= 10 || index === 0 ? Math.round(n) : n.toFixed(1)} ${units[index]}`;
}

function resourceSummary(resource?: ResourceRecord): string[] {
  if (!resource) return [];
  const peak = formatBytes(resource.systemd?.memory_peak_bytes);
  const limit = formatBytes(resource.limits?.memory_max_bytes);
  const available = formatBytes(resource.final_host?.mem_available_bytes);
  const items: string[] = [];
  if (peak || limit) items.push(`RAM ${peak ?? "—"}/${limit ?? "—"}`);
  if (available) items.push(`host free ${available}`);
  if (resource.queue_wait_seconds && resource.queue_wait_seconds > 0) {
    items.push(`queued ${resource.queue_wait_seconds.toFixed(1)}s`);
  }
  if (resource.resource_cause) items.push(`resource ${resource.resource_cause}`);
  return items;
}

export function AgentTimeline({ compact = false }: { compact?: boolean }) {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [offline, setOffline] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/jobs?limit=16", { cache: "no-store" });
      if (!response.ok) throw new Error("agent unavailable");
      const data = (await response.json()) as {
        agent?: { jobs?: JobRecord[] };
        jobs?: JobRecord[];
      };
      const next = data.agent?.jobs || data.jobs || [];
      setJobs(next);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    let disposed = false;
    let inFlight = false;
    let pending = false;
    let debounceTimer: number | undefined;
    let pollTimer: number | undefined;

    const runRefresh = async () => {
      if (disposed || inFlight) {
        pending = true;
        return;
      }
      inFlight = true;
      try {
        await refresh();
      } finally {
        inFlight = false;
        if (pending) {
          pending = false;
          scheduleRefresh();
        }
      }
    };

    const scheduleRefresh = () => {
      if (disposed || debounceTimer !== undefined) return;
      debounceTimer = window.setTimeout(() => {
        debounceTimer = undefined;
        void runRefresh();
      }, 180);
    };

    const onAgentEvent = () => scheduleRefresh();
    const schedulePoll = () => {
      if (disposed) return;
      pollTimer = window.setTimeout(() => {
        pollTimer = undefined;
        scheduleRefresh();
        schedulePoll();
      }, document.visibilityState === "visible" ? 5000 : 30000);
    };
    const onVisibilityChange = () => {
      if (pollTimer !== undefined) window.clearTimeout(pollTimer);
      pollTimer = undefined;
      schedulePoll();
    };
    window.addEventListener("pdflow:agent-event", onAgentEvent);
    document.addEventListener("visibilitychange", onVisibilityChange);
    void runRefresh();
    // The shared runtime status provider already receives SSE updates. This
    // low-frequency poll is only a recovery path for a dock opened directly
    // or when the event stream is unavailable.
    schedulePoll();
    return () => {
      disposed = true;
      window.removeEventListener("pdflow:agent-event", onAgentEvent);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      if (pollTimer !== undefined) window.clearTimeout(pollTimer);
      if (debounceTimer !== undefined) window.clearTimeout(debounceTimer);
    };
  }, [refresh]);

  async function cancel(job: JobRecord) {
    await fetch("/api/jobs/" + encodeURIComponent(job.job_id) + "/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).catch(() => undefined);
    void refresh();
  }

  return (
    <section className={clsx("agent-timeline", compact && "agent-timeline-compact")}>
      <div className="agent-timeline-head">
        <div>
          <p className="studio-pro-eyebrow">Runtime provenance</p>
          <h2>Local agent timeline</h2>
        </div>
        <span className={clsx("pill", offline ? "bad" : "ok")}>
          {offline ? "AGENT GAP" : "LIVE"}
        </span>
      </div>
      {jobs.length === 0 ? (
        <p className="muted">
          {offline
            ? "Start the local agent to see jobs, PIDs, logs and report links."
            : "No jobs in this session."}
        </p>
      ) : (
        <div className="agent-timeline-list">
          {jobs.map((job) => (
            <article key={job.job_id} className="agent-timeline-row">
              <div className="agent-timeline-status">
                <span className={clsx("pill", tone(job.state))}>{job.state}</span>
                <strong>{label(job)}</strong>
                <small>{job.operation}</small>
              </div>
              <div className="agent-timeline-meta">
                {job.pid ? <span>PID {job.pid}</span> : null}
                {job.timeout_seconds ? <span>timeout {job.timeout_seconds}s</span> : null}
                {job.artifact?.authority ? (
                  <span>{job.artifact.authority.toUpperCase()}</span>
                ) : null}
                {resourceSummary(job.resource).map((item) => (
                  <span key={item}>{item}</span>
                ))}
                {job.termination_cause ? (
                  <span className="agent-timeline-cause">cause {job.termination_cause}</span>
                ) : null}
                {job.state === "RUNNING" || job.state === "QUEUED" ? (
                  <button type="button" className="btn-danger btn-sm" onClick={() => void cancel(job)}>
                    Stop
                  </button>
                ) : null}
              </div>
              {job.reason ? <p className="agent-timeline-reason">{job.reason}</p> : null}
              {job.report?.report_id ? (
                <a
                  className="agent-timeline-report"
                  href={"/reports/" + encodeURIComponent(job.report.report_id)}
                >
                  report {job.report.report_id.slice(-12)}
                  {job.report.stale ? " · STALE" : ""}
                </a>
              ) : null}
              {job.log_path ? (
                <a
                  className="agent-timeline-report"
                  href={"/api/jobs/" + encodeURIComponent(job.job_id) + "/log"}
                  download
                >
                  download complete log
                </a>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

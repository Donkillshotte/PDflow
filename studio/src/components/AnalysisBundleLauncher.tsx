"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown, ListChecks, Play, RefreshCw } from "lucide-react";
import clsx from "clsx";
import type { AnalysisBundlePlan } from "@/lib/pdflowContracts";

const FLOW_BUNDLES = [
  ["recommended", "Recommended checkpoint checks"],
  ["final_timing", "Final timing"],
  ["final_power_integrity", "Final power integrity"],
  ["gds_verification", "GDS verification"],
  ["product_signoff", "Product signoff prerequisites"],
] as const;

const LAB_BUNDLES = [
  ["recommended", "Recommended checkpoint checks"],
  ["final_timing", "Timing evidence"],
  ["final_power_integrity", "Power integrity evidence"],
] as const;

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  return `${Math.ceil(seconds / 60)} min`;
}

export function AnalysisBundleLauncher({
  stage,
  variant,
  runId,
  onQueued,
}: {
  stage: string;
  variant: string;
  runId?: string | null;
  onQueued?: () => void;
}) {
  const [bundleId, setBundleId] = useState("recommended");
  const [plan, setPlan] = useState<AnalysisBundlePlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [queueing, setQueueing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const options = variant.startsWith("lab_asap7_") ? LAB_BUNDLES : FLOW_BUNDLES;

  async function preview() {
    setLoading(true);
    setMessage(null);
    let lastError: unknown = null;
    // Preview is read-only, so a short retry is safe when the desktop agent
    // is restarting or a previous metadata request is being released. Do not
    // retry queue/execute requests here: this loop can never create a run or
    // a native process.
    try {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          const response = await fetch("/api/analysis-bundles/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bundle_id: bundleId, stage, variant, run_id: runId ?? undefined }),
          });
          const body = (await response.json().catch(() => null)) as AnalysisBundlePlan | { reason?: string } | null;
          if (response.ok) {
            setPlan(body as AnalysisBundlePlan);
            return;
          }
          lastError = new Error(body && "reason" in body ? body.reason : `preflight HTTP ${response.status}`);
          if (response.status !== 503 || attempt === 2) break;
        } catch (error) {
          lastError = error;
          if (attempt === 2) break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 400 * (attempt + 1)));
      }
    } finally {
      setLoading(false);
    }
    setPlan(null);
    setMessage(lastError instanceof Error ? lastError.message : "analysis preflight unavailable");
  }

  async function queueBundle() {
    if (!plan?.ready || queueing) return;
    setQueueing(true);
    setMessage(null);
    try {
      const response = await fetch("/api/analysis-bundles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bundle_id: bundleId,
          stage,
          variant,
          run_id: runId ?? undefined,
          confirm: true,
        }),
      });
      const body = (await response.json().catch(() => null)) as { status?: string; reason?: string } | null;
      if (!response.ok || body?.status !== "QUEUED") {
        throw new Error(body?.reason || `bundle queue HTTP ${response.status}`);
      }
      setMessage("Bundle queued in the single native-job queue.");
      setPlan(null);
      onQueued?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "analysis bundle could not be queued");
    } finally {
      setQueueing(false);
    }
  }

  return (
    <section className="analysis-bundle-launcher" aria-label="Analysis bundle preflight">
      <div className="analysis-bundle-heading">
        <div>
          <span className="workspace-panel-kicker">Explicit preflight</span>
          <h3><ListChecks size={15} aria-hidden /> Analysis bundle</h3>
        </div>
        <span className="analysis-bundle-readonly">read-only plan</span>
      </div>
      <div className="analysis-bundle-controls">
        <label htmlFor="analysis-bundle-select">Bundle</label>
        <select
          id="analysis-bundle-select"
          value={bundleId}
          onChange={(event) => {
            setBundleId(event.target.value);
            setPlan(null);
            setMessage(null);
          }}
        >
          {options.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <button type="button" className="btn-ghost btn-sm" onClick={() => void preview()} disabled={loading}>
          {loading ? <RefreshCw size={13} className="fl-spin" aria-hidden /> : <ChevronDown size={13} aria-hidden />}
          {loading ? "Planning…" : "Preview"}
        </button>
      </div>
      {message && <p className="analysis-bundle-message" role="status">{message}</p>}
      {plan && (
        <div className="analysis-bundle-plan">
          <div className="analysis-bundle-summary">
            <span className={clsx("analysis-bundle-state", plan.ready ? "ready" : "blocked")}>
              {plan.ready ? "Ready" : "Blocked"}
            </span>
            <span>{plan.jobs.length} job{plan.jobs.length === 1 ? "" : "s"}</span>
            <span>~{formatDuration(plan.estimated_duration_seconds)}</span>
            <span>{plan.resource_limit.queue}</span>
          </div>
          <ul className="analysis-bundle-jobs">
            {plan.jobs.map((job) => (
              <li key={job.check_id} className={clsx(!job.runnable && "blocked")}>
                <span>{job.display_name || job.check_id}</span>
                <code>{job.runnable ? job.action : job.reason || "blocked"}</code>
              </li>
            ))}
          </ul>
          {plan.downstream_invalidations.length > 0 && (
            <p className="analysis-bundle-impact">
              <AlertTriangle size={13} aria-hidden /> Revalidates: {plan.downstream_invalidations.join(" · ")}
            </p>
          )}
          <button type="button" className="btn-primary btn-sm" disabled={!plan.ready || queueing} onClick={() => void queueBundle()}>
            <Play size={13} aria-hidden />
            {queueing ? "Queueing…" : "Confirm & queue"}
          </button>
        </div>
      )}
      <p className="analysis-bundle-note">Preview never launches a process. Confirmation submits native jobs through the local agent.</p>
    </section>
  );
}

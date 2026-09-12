"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useToast } from "@/components/ToastProvider";
import type { PackageEvidence, PathLedger } from "@/lib/pdflowContracts";
import { SystemPdnVisual } from "@/components/flowlab/SystemPdnVisual";

type HookRow = { id: string; label: string; ok: boolean; detail: string };

const EVIDENCE_STATUSES = new Set(["PASS", "FAIL", "WARN", "PARTIAL", "PROXY"]);

type AgentReport = {
  ok?: boolean;
  status?: string;
  evidence_status?: string;
  signoff_status?: string;
  reason?: string;
};

function hasCompletedEvidence(state: string, report?: AgentReport): boolean {
  const status = String(report?.status || "").toUpperCase();
  return (
    state === "COMPLETED" &&
    EVIDENCE_STATUSES.has(status) &&
    report?.evidence_status !== "GAP"
  );
}

function statusClass(status?: string) {
  return status === "PASS"
    ? "ok"
    : status === "FAIL" || status === "GAP"
      ? "bad"
      : "warn";
}

export type SystemPreview = {
  summary?: string;
  transient?: { droop_mv?: number };
  impedance?: { z_max_mohm?: number };
};

export type ThermalPreview = {
  summary?: string;
  thermal?: { t_max_c?: number; engine?: string };
};

export type PkgPreview = {
  summary?: string;
  steps?: { pkg_rdl?: { summary?: string; ok?: boolean } };
};

const PKG_HOOKS = [
  "system_pdn",
  "thermal_signoff",
  "pkg_rdl",
  "pkg_signoff",
  "signoff_phase2",
];

export function PkgHubPanel({
  initialSystem = null,
  initialThermal = null,
  initialPkg = null,
  initialHooks = [],
}: {
  initialSystem?: SystemPreview | null;
  initialThermal?: ThermalPreview | null;
  initialPkg?: PkgPreview | null;
  initialHooks?: HookRow[];
}) {
  const { push } = useToast();
  const [hooks, setHooks] = useState<HookRow[]>(initialHooks);
  const [systemReport, setSystemReport] = useState<SystemPreview | null>(initialSystem);
  const [thermalReport, setThermalReport] = useState<ThermalPreview | null>(initialThermal);
  const [pkgReport, setPkgReport] = useState<PkgPreview | null>(initialPkg);
  const [evidence, setEvidence] = useState<PackageEvidence | null>(null);
  const [pathLedger, setPathLedger] = useState<PathLedger | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [suite, evidenceResponse, ledgerResponse, sys, thermal, pkg] = await Promise.all([
        fetch("/api/suite").then((r) => r.json()),
        fetch("/api/package"),
        fetch("/api/path-ledger"),
        fetch("/api/content?path=sim/reports/system_pdn_flowlab.json").then((r) =>
          r.ok ? r.json() : null,
        ),
        fetch("/api/content?path=sim/reports/thermal_signoff_flowlab.json").then((r) =>
          r.ok ? r.json() : null,
        ),
        fetch("/api/content?path=sim/reports/pkg_signoff_flowlab.json").then((r) =>
          r.ok ? r.json() : null,
        ),
      ]);
      if (evidenceResponse.ok) {
        setEvidence((await evidenceResponse.json()) as PackageEvidence);
      }
      if (ledgerResponse.ok) {
        setPathLedger((await ledgerResponse.json()) as PathLedger);
      }
      const pkgHooks = (suite.hooks ?? []).filter((h: HookRow) =>
        PKG_HOOKS.includes(h.id),
      );
      setHooks(pkgHooks);
      if (sys?.content) {
        try {
          setSystemReport(JSON.parse(sys.content));
        } catch {
          setSystemReport(null);
        }
      }
      if (thermal?.content) {
        try {
          setThermalReport(JSON.parse(thermal.content));
        } catch {
          setThermalReport(null);
        }
      }
      if (pkg?.content) {
        try {
          setPkgReport(JSON.parse(pkg.content));
        } catch {
          setPkgReport(null);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Package evidence unavailable");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const systemStep = evidence?.steps.system_pdn;
  const packageStatus = evidence?.status || "NOT_RUN";

  async function runAction(action: string, long: boolean) {
    if (busy) return;
    if (long && !window.confirm(`Start ${action}? This may take several minutes.`)) {
      return;
    }
    setBusy(action);
    const ac = new AbortController();
    try {
      const agentStart = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          operation: "action",
          variant: "flowlab",
          mode: "view",
        }),
        signal: ac.signal,
      });
      if (agentStart.status !== 503) {
        if (!agentStart.ok) {
          const message = await agentStart.text();
          throw new Error(message || "Agent rejected " + action);
        }
        let job = (await agentStart.json()) as {
          job_id: string;
          state: string;
          reason?: string;
          report?: AgentReport;
        };
        while (job.state === "QUEUED" || job.state === "RUNNING") {
          await new Promise((resolve) => window.setTimeout(resolve, 500));
          const jobResponse = await fetch(
            "/api/jobs/" + encodeURIComponent(job.job_id),
            { signal: ac.signal },
          );
          if (!jobResponse.ok) throw new Error("Agent job status unavailable");
          job = (await jobResponse.json()) as typeof job;
        }
        const ok = job.state === "COMPLETED" && job.report?.ok === true;
        const evidence = hasCompletedEvidence(job.state, job.report);
        const status = String(job.report?.status || "").toUpperCase();
        push(
          ok
            ? action + " completed"
            : evidence
              ? `${action} completed · ${status} evidence (not Product signoff)`
              : job.reason || action + " " + job.state.toLowerCase(),
          ok ? "ok" : evidence ? "info" : "bad",
        );
        await refresh();
        return;
      }
      const res = await fetch(
        `/api/run/stream?action=${encodeURIComponent(action)}&mode=flowlab`,
        { signal: ac.signal },
      );
      if (!res.ok || !res.body) throw new Error("Stream not available");
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let ok = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = dec.decode(value);
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6)) as { type: string; ok?: boolean };
            if (ev.type === "done") ok = Boolean(ev.ok);
          } catch {
            /* ignore */
          }
        }
      }
      push(ok ? `${action} completed` : `${action} failed`, ok ? "ok" : "bad");
      void refresh();
    } catch (e) {
      push(e instanceof Error ? e.message : "Run error", "bad");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="pkg-hub-panel panel" id="system-pdn">
      <header className="pkg-hub-head">
        <h2>System PDN and Phase 2</h2>
        <p>
          Package ladder, HotSpot, and dummy RDL. STA · DRC · LVS · chip IR
          stay on{" "}
          <Link href="/flow?phase=finish#signoff">finish</Link>. DSE stays on{" "}
          <Link href="/lab">/lab</Link>.
        </p>
      </header>

      <div className="pkg-live-strip">
        <span className={"pill " + statusClass(packageStatus)}>
          PACKAGE {packageStatus}
        </span>
        <span className="muted">
          Current finish snapshot · no historical baseline · read-only surface
        </span>
        <span className="pkg-provenance">
          mesh {pathLedger?.mesh_id || "not available"}
        </span>
      </div>

      {error && (
        <p className="block-banner" role="alert">
          Package evidence unavailable: {error}
        </p>
      )}

      <ul className="pkg-hook-list">
        {hooks.map((h) => (
          <li key={h.id} className={h.ok ? "pkg-hook-ok" : "pkg-hook-pending"}>
            <span>{h.ok ? "✓" : "○"}</span>
            <div>
              <strong>{h.label}</strong>
              <small>{h.detail}</small>
            </div>
          </li>
        ))}
      </ul>

      <div className="pkg-report-grid">
        <article className="pkg-report-card">
          <h3>System PDN</h3>
          {systemStep?.summary || systemReport?.summary ? (
            <>
              <p>{systemStep?.summary || systemReport?.summary}</p>
              <p className="pkg-metrics">
                <span className={"pill " + statusClass(systemStep?.status)}>
                  {systemStep?.status || "LEGACY"}
                </span>{" "}
                Droop{" "}
                {systemStep?.droop_mv?.toFixed(2) ??
                  systemReport?.transient?.droop_mv?.toFixed(2) ??
                  "—"}{" "}
                mV · Zmax{" "}
                {systemStep?.zmax_mohm?.toFixed(2) ??
                  systemReport?.impedance?.z_max_mohm?.toFixed(2) ??
                  "—"}{" "}
                mΩ
              </p>
              {systemStep?.reason && <p className="muted">{systemStep.reason}</p>}
            </>
          ) : (
            <p>Report missing — run System PDN here after four-pillar signoff.</p>
          )}
        </article>
        <article className="pkg-report-card">
          <h3>Phase 2</h3>
          {thermalReport?.summary || pkgReport?.summary ? (
            <>
              <p>{thermalReport?.summary ?? "HotSpot report missing."}</p>
              <p className="pkg-metrics">
                t_max {thermalReport?.thermal?.t_max_c?.toFixed(2) ?? "—"} °C ·{" "}
                {pkgReport?.steps?.pkg_rdl?.summary ?? "dummy RDL not stamped"}
              </p>
            </>
          ) : (
            <p>Reports missing — run thermal_signoff and pkg_signoff.</p>
          )}
        </article>
      </div>

      <SystemPdnVisual reportPath="sim/reports/system_pdn_flowlab.json" />

      <div className="pkg-ledger-card">
        <div>
          <strong>Path / IR ledger</strong>
          <p className="muted">
            Timing and power evidence stay tied to the current finish and to
            distinct mesh identities.
          </p>
        </div>
        <div className="pkg-ledger-status">
          <span className={"pill " + statusClass(pathLedger?.status)}>
            {pathLedger?.status || "NOT_RUN"}
          </span>
          <span>
            {pathLedger?.entries?.length || 0} paths ·{" "}
            {pathLedger?.meshes?.length || 0} meshes
          </span>
        </div>
      </div>

      <p className="pkg-hub-links">
        <button
          type="button"
          className="btn-primary"
          disabled={Boolean(busy)}
          onClick={() => void runAction("system_pdn", false)}
        >
          {busy === "system_pdn" ? "Running…" : "Run System PDN"}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={Boolean(busy)}
          onClick={() => void runAction("signoff_phase2", true)}
        >
          {busy === "signoff_phase2" ? "Running…" : "Run Phase 2"}
        </button>
      </p>
    </section>
  );
}

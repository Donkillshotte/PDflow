"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { Activity, ExternalLink, PackageOpen, RefreshCw, ShieldCheck } from "lucide-react";
import { FlowLabLayoutCanvas } from "@/components/flowlab/FlowLabLayoutCanvas";
import { SystemPdnVisual } from "@/components/flowlab/SystemPdnVisual";
import { LiveRunConsole } from "@/components/LiveRunConsole";

const DEFAULT_VARIANT = "lab_asap7_gcd_tc_rvt_nldm_7p5";
const SAFE_VARIANT = /^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$/;

type Asap7PackageSnapshot = {
  variant?: string | null;
  design?: string | null;
  corner?: string | null;
  track?: string | null;
  pkg?: {
    ok?: boolean;
    status?: string | null;
    nBumps?: number | null;
    droopMv?: number | null;
    vdd?: number | null;
    rdlOk?: boolean;
  } | null;
  chipPdn?: {
    ok?: boolean;
    status?: string | null;
    meshStaticMv?: number | null;
    meshTransientMv?: number | null;
  } | null;
  stages?: Record<string, { done?: boolean }> | null;
};

type LabResponse = { asap7?: Asap7PackageSnapshot | null };

function format(value: unknown, digits = 2): string {
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString(undefined, { maximumFractionDigits: digits })
    : "—";
}

type DisplayStatus = "PASS" | "FAIL" | "WARN" | "PARTIAL" | "PROXY" | "GAP" | "NOT RUN";

function statusOf(value: { ok?: boolean; status?: string | null } | null | undefined): DisplayStatus {
  if (!value) return "NOT RUN";
  const reported = String(value.status ?? "").toUpperCase();
  if (["PASS", "FAIL", "WARN", "PARTIAL", "PROXY", "GAP", "NOT_RUN"].includes(reported)) {
    return reported as DisplayStatus;
  }
  return value.ok === true ? "PASS" : "FAIL";
}

export function Asap7PackagePanel({ initialVariant }: { initialVariant?: string }) {
  const selectedInitialVariant = initialVariant && SAFE_VARIANT.test(initialVariant) ? initialVariant : null;
  const [snapshot, setSnapshot] = useState<Asap7PackageSnapshot | null>(null);
  const [variant, setVariant] = useState(selectedInitialVariant || DEFAULT_VARIANT);
  const requestedVariant = selectedInitialVariant;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/lab", { cache: "no-store" });
      if (!response.ok) throw new Error(`request failed (${response.status})`);
      const body = (await response.json()) as LabResponse;
      const next = body.asap7 ?? null;
      setSnapshot(next);
      if (!requestedVariant && next?.variant) setVariant(next.variant);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "unknown error");
    } finally {
      setLoading(false);
    }
  }, [requestedVariant]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onEvent = (event: Event) => {
      const detail = (event as CustomEvent<{ type?: string }>).detail;
      if (["tool.completed", "tool.failed", "artifact.changed", "report.updated"].includes(detail?.type ?? "")) {
        setRefreshKey((value) => value + 1);
        void refresh();
      }
    };
    window.addEventListener("pdflow:agent-event", onEvent);
    return () => window.removeEventListener("pdflow:agent-event", onEvent);
  }, [refresh]);

  const finishReady = snapshot?.stages?.finish?.done === true;
  const pkgStatus = statusOf(snapshot?.pkg);
  const chipStatus = statusOf(snapshot?.chipPdn);

  return (
    <div className="asap7-package-panel">
      <header className="asap7-package-header">
        <div>
          <span className="workspace-panel-kicker">ASAP7 · package / system PDN</span>
          <h2>Native package analysis workspace</h2>
          <p>System PDN uses the selected ASAP7 finish and the native SPICE engine when available. Package evidence remains isolated from Product.</p>
        </div>
        <div className="asap7-package-actions">
          <span className="pill neutral">{variant}</span>
          <button type="button" className="btn-ghost btn-sm" onClick={() => { setRefreshKey((value) => value + 1); void refresh(); }}>
            <RefreshCw size={13} aria-hidden /> {loading ? "Refreshing…" : "Refresh"}
          </button>
          <Link href={`/flow?platform=asap7&phase=finish&variant=${encodeURIComponent(variant)}`} className="btn-ghost btn-sm"><ExternalLink size={13} aria-hidden /> Finish</Link>
        </div>
      </header>

      {error ? <p className="block-banner" role="alert">Package evidence unavailable: {error}</p> : null}

      <div className="asap7-package-grid">
        <section className="asap7-package-canvas" aria-label="ASAP7 finish layout">
          <div className="asap7-package-canvas-label">
            <span><PackageOpen size={14} aria-hidden /> Die / package reference</span>
            <span className={clsx("pill", finishReady ? "ok" : "warn")}>{finishReady ? "ODB + GDS ready" : "finish not run"}</span>
          </div>
          <FlowLabLayoutCanvas phaseId="pkg" variant={variant} refreshKey={refreshKey} stageDone={finishReady} allowCandidate={false} />
        </section>

        <aside className="asap7-package-inspector" aria-label="System PDN evidence">
          <section className="asap7-package-section">
            <div className="asap7-package-section-heading">
              <div>
                <span className="workspace-panel-kicker">System PDN</span>
                <h3>{pkgStatus}</h3>
              </div>
              <Activity size={15} aria-hidden />
            </div>
            <div className="asap7-package-metrics">
              <div><span>VDD</span><strong>{format(snapshot?.pkg?.vdd, 3)} V</strong></div>
              <div><span>System droop</span><strong>{format(snapshot?.pkg?.droopMv)} mV</strong></div>
              <div><span>Bumps</span><strong>{format(snapshot?.pkg?.nBumps, 0)}</strong></div>
              <div><span>RDL</span><strong>{snapshot?.pkg?.rdlOk == null ? "—" : snapshot.pkg.rdlOk ? "valid" : "fail"}</strong></div>
            </div>
            <p className="asap7-package-note"><ShieldCheck size={13} aria-hidden /> <code>GAP</code>/<code>NOT RUN</code> is kept explicit; a package result cannot close Product.</p>
          </section>

          <section className="asap7-package-section">
            <div className="asap7-package-section-heading">
              <div>
                <span className="workspace-panel-kicker">Chip PDN mesh</span>
                <h3>{chipStatus}</h3>
              </div>
            </div>
            <div className="asap7-package-metrics">
              <div><span>Static</span><strong>{format(snapshot?.chipPdn?.meshStaticMv)} mV</strong></div>
              <div><span>Transient</span><strong>{format(snapshot?.chipPdn?.meshTransientMv)} mV</strong></div>
            </div>
            <p className="asap7-package-note">On-die <code>write_pg_spice</code> mesh and System PDN are separate analyses. Both remain Lab-scoped.</p>
          </section>

          <SystemPdnVisual
            reportPath="sim/reports/lab_asap7_system_pdn.json"
            refreshKey={refreshKey}
            compact
          />

          <section className="asap7-package-section asap7-package-runner">
            <div className="asap7-package-section-heading">
              <div>
                <span className="workspace-panel-kicker">Native operations</span>
                <h3>Run package experiments</h3>
              </div>
            </div>
            <LiveRunConsole
              defaultAction="lab_asap7_pkg"
              agentVariant={variant}
              allowedActions={["lab_asap7_pkg", "lab_asap7_chip_pdn"]}
              onFinished={() => {
                setRefreshKey((value) => value + 1);
                window.setTimeout(() => void refresh(), 500);
              }}
            />
          </section>
        </aside>
      </div>
    </div>
  );
}

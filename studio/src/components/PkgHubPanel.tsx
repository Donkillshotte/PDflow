"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useToast } from "@/components/ToastProvider";

type HookRow = { id: string; label: string; ok: boolean; detail: string };

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
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [suite, sys, thermal, pkg] = await Promise.all([
      fetch("/api/suite").then((r) => r.json()),
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
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function runAction(action: string, long: boolean) {
    if (busy) return;
    if (long && !window.confirm(`Start «${action}»? This may take several minutes.`)) {
      return;
    }
    setBusy(action);
    const ac = new AbortController();
    try {
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
          {systemReport?.summary ? (
            <>
              <p>{systemReport.summary}</p>
              <p className="pkg-metrics">
                Droop {systemReport.transient?.droop_mv?.toFixed(2) ?? "—"} mV · Zmax{" "}
                {systemReport.impedance?.z_max_mohm?.toFixed(2) ?? "—"} mΩ
              </p>
            </>
          ) : (
            <p>Report missing — run system_pdn after finish.</p>
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

      <p className="pkg-hub-links">
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

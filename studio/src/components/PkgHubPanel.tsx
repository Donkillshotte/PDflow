"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useToast } from "@/components/ToastProvider";

type HookRow = { id: string; label: string; ok: boolean; detail: string };

type ReportPreview = {
  summary?: string;
  transient?: { droop_mv?: number };
  impedance?: { z_max_mohm?: number; pass_target?: boolean | null };
};

export function PkgHubPanel() {
  const { push } = useToast();
  const [hooks, setHooks] = useState<HookRow[]>([]);
  const [systemReport, setSystemReport] = useState<ReportPreview | null>(null);
  const [chipReport, setChipReport] = useState<ReportPreview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [suite, sys, chip] = await Promise.all([
      fetch("/api/suite").then((r) => r.json()),
      fetch("/api/content?path=sim/reports/system_pdn_flowlab.json").then((r) =>
        r.ok ? r.json() : null,
      ),
      fetch("/api/content?path=sim/reports/pdn_chip_ir_flowlab.json").then((r) =>
        r.ok ? r.json() : null,
      ),
    ]);
    const powerHooks = (suite.hooks ?? []).filter((h: HookRow) =>
      [
        "activity",
        "chip_pdn_ir",
        "vyges_em_ir",
        "dynamic_ir",
        "system_pdn",
        "power_chain",
        "spice_lab",
        "ngspice",
        "sta_signoff",
        "sta_ir_aware",
        "drc_signoff",
        "lvs_signoff",
        "power_signoff",
        "signoff_all",
      ].includes(h.id),
    );
    setHooks(powerHooks);
    if (sys?.content) {
      try {
        setSystemReport(JSON.parse(sys.content));
      } catch {
        setSystemReport(null);
      }
    }
    if (chip?.content) {
      try {
        setChipReport(JSON.parse(chip.content));
      } catch {
        setChipReport(null);
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function runSignoff(action: string, long: boolean) {
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
    <section className="pkg-hub-panel panel">
      <header className="pkg-hub-head">
        <h2>Power chain status</h2>
        <p>
          FlowLab reports for the power chain. Signoff stays on{" "}
          <Link href="/flow?phase=finish#signoff">finish</Link>. DSE stays on{" "}
          <Link href="/lab">/lab</Link>.{" "}
          <Link href="/flow?phase=pkg">FlowLab PKG →</Link>
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
            <p>Report missing — run system_pdn or power_chain.</p>
          )}
        </article>
        <article className="pkg-report-card">
          <h3>Chip IR mesh</h3>
          {(chipReport as { summary?: string } | null)?.summary ? (
            <p>{(chipReport as { summary: string }).summary}</p>
          ) : (
            <p>Report missing — run chip_pdn_ir after finish.</p>
          )}
        </article>
      </div>

      <p className="pkg-hub-links">
        <button
          type="button"
          className="btn-primary"
          disabled={Boolean(busy)}
          onClick={() => void runSignoff("power_chain", true)}
        >
          {busy === "power_chain" ? "Running…" : "Run power chain"}
        </button>
      </p>
    </section>
  );
}

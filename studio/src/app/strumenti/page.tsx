"use client";

import { useEffect, useState } from "react";
import { LiveRunConsole } from "@/components/LiveRunConsole";
import { ResultsPanel } from "@/components/ResultsPanel";
import { OpsDashboard } from "@/components/OpsDashboard";

type Tool = { name: string; ok: boolean; detail: string };
type Status = {
  tools: Tool[];
  orfs: boolean;
  tutorial: boolean;
  ready: boolean;
};

export default function StrumentiPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [stage, setStage] = useState("synth");
  const [refreshKey, setRefreshKey] = useState(0);
  const [opsKey, setOpsKey] = useState(0);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const res = await fetch("/api/toolchain");
      setStatus(await res.json());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <main>
      <header className="page-head">
        <h1>Strumenti</h1>
        <p>
          Console operativa enterprise: single-flight lock, dipendenze di fase,
          conferma per job lunghi, storico, export log e pipeline live.
        </p>
      </header>

      <div className="lesson-actions">
        <button type="button" className="btn-ghost" onClick={refresh} disabled={loading}>
          {loading ? "Aggiorno…" : "Aggiorna toolchain"}
        </button>
        {status?.ready ? (
          <span className="pill ok">ambiente pronto</span>
        ) : status ? (
          <span className="pill bad">manca qualcosa</span>
        ) : (
          <span className="pill">…</span>
        )}
      </div>

      <div className="tool-grid">
        {(status?.tools ?? []).map((t) => (
          <div key={t.name} className="tool-card">
            <strong>
              {t.name}{" "}
              <span className={`pill ${t.ok ? "ok" : "bad"}`}>
                {t.ok ? "ok" : "no"}
              </span>
            </strong>
            <span>{t.detail}</span>
          </div>
        ))}
        <div className="tool-card">
          <strong>
            ORFS{" "}
            <span className={`pill ${status?.orfs ? "ok" : "bad"}`}>
              {status?.orfs ? "ok" : "no"}
            </span>
          </strong>
          <span>tools/OpenROAD-flow-scripts/flow</span>
        </div>
        <div className="tool-card">
          <strong>
            Tutorial GCD{" "}
            <span className={`pill ${status?.tutorial ? "ok" : "bad"}`}>
              {status?.tutorial ? "ok" : "no"}
            </span>
          </strong>
          <span>learn/designs/nangate45/gcd-tutorial</span>
        </div>
      </div>

      <section className="panel" style={{ marginBottom: "1.2rem" }}>
        <OpsDashboard refreshKey={opsKey} />
      </section>

      <section className="panel" style={{ marginBottom: "1.2rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          Console live
        </h2>
        <LiveRunConsole
          onFinished={(_ok, action) => {
            if (
              ["synth", "floorplan", "place", "cts", "route", "finish"].includes(
                action,
              )
            ) {
              setStage(action);
              setRefreshKey((k) => k + 1);
            }
            setOpsKey((k) => k + 1);
          }}
        />
      </section>

      <section className="panel">
        <ResultsPanel stage={stage} refreshKey={refreshKey} />
      </section>
    </main>
  );
}

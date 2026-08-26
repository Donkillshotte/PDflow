"use client";

import { useEffect, useState } from "react";
import { RunConsole } from "@/components/RunConsole";

type Tool = { name: string; ok: boolean; detail: string };
type Status = {
  tools: Tool[];
  orfs: boolean;
  tutorial: boolean;
  ready: boolean;
};

export default function StrumentiPage() {
  const [status, setStatus] = useState<Status | null>(null);

  async function refresh() {
    const res = await fetch("/api/toolchain");
    setStatus(await res.json());
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <main>
      <header className="page-head">
        <h1>Strumenti</h1>
        <p>
          Stato della toolchain e azioni sicure sul wrapper del corso. Non serve
          memorizzare i path: scegli un’azione e leggi l’output qui sotto.
        </p>
      </header>

      <div className="lesson-actions">
        <button type="button" className="btn-ghost" onClick={refresh}>
          Aggiorna stato
        </button>
        {status?.ready ? (
          <span className="pill ok">ambiente pronto</span>
        ) : (
          <span className="pill bad">manca qualcosa</span>
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

      <section className="panel">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          Console azioni
        </h2>
        <RunConsole />
      </section>
    </main>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";

type EcoStep = {
  step?: string;
  args?: string;
  reason?: string;
  enabled?: boolean;
};

type EcoReport = {
  ok?: boolean;
  mode?: string;
  summary?: string;
  signoff?: boolean;
  signoff_required?: string;
  locked?: boolean;
  proposed?: EcoStep[];
  error?: string;
};

export function EcoPanel() {
  const [report, setReport] = useState<EcoReport | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/report?name=eco_flowlab.json", { cache: "no-store" });
      if (!res.ok) return;
      setReport(await res.json());
    } catch {
      /* report is optional until eco has been run */
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="fl-card" id="eco">
      <header className="fl-card-head">
        <h3>ECO</h3>
        <p className="muted">
          Propose post-finish timing repair. Apply is refused on locked variants
          (`flowlab` / `learn` / `base`). Does not replace signoff.
        </p>
      </header>
      {report ? (
        <dl className="fl-kv">
          <div>
            <dt>Mode</dt>
            <dd>{report.mode ?? "—"}</dd>
          </div>
          <div>
            <dt>Claims signoff</dt>
            <dd>{report.signoff ? "yes (bug)" : "no"}</dd>
          </div>
          <div>
            <dt>Next</dt>
            <dd>
              <code>{report.signoff_required ?? "learn/scripts/run_signoff_all.sh"}</code>
            </dd>
          </div>
        </dl>
      ) : (
        <p className="muted">No ECO report yet. Run the eco action after finish.</p>
      )}
      {report?.error ? <p className="muted">{report.error}</p> : null}
      {report?.proposed?.length ? (
        <table className="fl-table">
          <thead>
            <tr>
              <th>Step</th>
              <th>Args</th>
              <th>On</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {report.proposed.map((step, i) => (
              <tr key={`${step.step}-${i}`}>
                <td>
                  <code>{step.step}</code>
                </td>
                <td>
                  <code>{step.args || "—"}</code>
                </td>
                <td>{step.enabled ? "yes" : "no"}</td>
                <td>{step.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

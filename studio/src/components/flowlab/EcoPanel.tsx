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
    <section className="fl-dynir" id="eco" aria-label="ECO propose">
      <header className="fl-dynir-head">
        <strong>ECO</strong>
        <p>
          Post-finish timing repair plan. Apply is refused on locked variants.
          Unlocked apply writes a sidecar ODB only — not GDS, SPEF, or
          verilog. Does not replace <code>signoff_all</code>.
        </p>
      </header>
      {report ? (
        <p className="fl-dynir-summary">
          {report.summary ?? report.mode} · signoff claim: {report.signoff ? "yes (bug)" : "no"}
          {report.signoff_required ? ` · next ${report.signoff_required}` : ""}
        </p>
      ) : (
        <p className="fl-dynir-empty">No ECO report yet. Run the eco action after finish.</p>
      )}
      {report?.error ? <p className="fl-dynir-empty">{report.error}</p> : null}
      {report?.proposed?.length ? (
        <ul className="lb-chips" aria-label="Proposed ECO steps">
          {report.proposed.map((step, i) => (
            <li key={`${step.step}-${i}`}>
              <span>
                {step.step}
                {step.args ? ` ${step.args}` : ""}
                {step.enabled ? "" : " (off)"}
              </span>
              <b>{step.reason}</b>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

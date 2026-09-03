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
  rewrote?: string[];
};

export function EcoPanel() {
  const [report, setReport] = useState<EcoReport | null>(null);
  const [apply, setApply] = useState<EcoReport | null>(null);
  const [close, setClose] = useState<EcoReport | null>(null);

  const load = useCallback(async () => {
    try {
      const [proposeRes, applyRes, closeRes] = await Promise.all([
        fetch("/api/report?name=eco_flowlab.json", { cache: "no-store" }),
        fetch("/api/report?name=eco_apply_eco_scratch.json", { cache: "no-store" }),
        fetch("/api/report?name=signoff_all_eco_scratch.json", { cache: "no-store" }),
      ]);
      if (proposeRes.ok) setReport(await proposeRes.json());
      if (applyRes.ok) setApply(await applyRes.json());
      if (closeRes.ok) setClose(await closeRes.json());
    } catch {
      /* reports are optional until eco / signoff_all have been run */
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
          Unlocked apply writes finish artifacts on a copy (ODB, DEF,
          verilog, CDL, GDS). Does not replace <code>signoff_all</code>.
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
      {apply ? (
        <p className="fl-dynir-summary">
          Apply ({apply.mode ?? "apply"}): {apply.summary ?? "—"}
          {apply.signoff ? " · claims signoff (bug)" : " · does not claim signoff"}
          {apply.rewrote?.length ? ` · wrote ${apply.rewrote.join("+")}` : ""}
        </p>
      ) : null}
      {close ? (
        <p className="fl-dynir-summary">
          Close on copy: {close.summary ?? "signoff_all"}
          {close.ok ? " · ok" : " · not ok"}
        </p>
      ) : null}
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

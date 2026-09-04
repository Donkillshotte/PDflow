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

type EcoApplyReport = EcoReport & {
  repaired?: boolean;
  leftover?: string;
};

type CloseReport = {
  ok?: boolean;
  summary?: string;
  leftover?: { must_connect?: number; circuits?: string[]; note?: string };
  setup_leftover?: {
    setup_open?: boolean;
    wns_ns?: number;
    clock_ns?: number;
    note?: string;
    wns_kind?: string;
    worst_endpoint?: string;
  };
  pillars?: Record<string, { ok?: boolean; summary?: string }>;
};

function stepState(ok: boolean | undefined, present: boolean): "ok" | "wait" | "fail" {
  if (!present) return "wait";
  if (ok) return "ok";
  return "fail";
}

function applyState(apply: EcoApplyReport | null): "ok" | "wait" | "fail" | "leftover" {
  if (!apply) return "wait";
  if (apply.ok === false) return "fail";
  if (apply.repaired === false || apply.leftover) return "leftover";
  return "ok";
}

function closeState(close: CloseReport | null): "ok" | "wait" | "fail" | "leftover" {
  if (!close) return "wait";
  if (close.ok === false) return "fail";
  if (close.leftover?.must_connect || close.setup_leftover?.setup_open) {
    return "leftover";
  }
  return "ok";
}

export function EcoPanel({
  busy,
  onRun,
}: {
  busy?: string | null;
  onRun?: (action: string, long: boolean) => void;
} = {}) {
  const [report, setReport] = useState<EcoReport | null>(null);
  const [apply, setApply] = useState<EcoApplyReport | null>(null);
  const [close, setClose] = useState<CloseReport | null>(null);

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

  const closePillars = close?.pillars
    ? Object.entries(close.pillars)
        .map(([name, pillar]) => `${name}:${pillar.ok ? "ok" : "fail"}`)
        .join(" · ")
    : "";

  return (
    <section className="fl-dynir" id="eco" aria-label="ECO loop">
      <header className="fl-dynir-head">
        <strong>ECO loop</strong>
        <p>
          Propose on the locked finish. Apply writes artifacts only on an
          unlocked copy. Size-up wraps DPL in incremental GRT, then
          detailed_route. If TritonRoute cannot connect (DRT-0206), apply
          restores the source. A legal size-up may still leave setup open
          — leftover is named. Close is <code>signoff_all</code> on that
          copy — ECO never skips it.
        </p>
      </header>
      <ol className="fl-eco-loop" aria-label="ECO propose, apply, close">
        <li data-state={stepState(report?.ok, Boolean(report))}>
          <span>1 · Propose</span>
          <b>{report ? (report.summary ?? "propose") : "no propose report yet"}</b>
          <em>
            flowlab · locked
            {report
              ? report.signoff
                ? " · claims signoff (bug)"
                : " · does not claim signoff"
              : ""}
            {report?.signoff_required ? ` · next ${report.signoff_required}` : ""}
          </em>
          {onRun ? (
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={() => onRun("eco", false)}
            >
              {busy === "eco" ? "Proposing…" : "Run propose"}
            </button>
          ) : null}
        </li>
        <li data-state={applyState(apply)}>
          <span>2 · Apply on copy</span>
          <b>{apply ? (apply.summary ?? "apply") : "no apply on eco_scratch yet"}</b>
          <em>
            eco_scratch · refused on flowlab/learn/base
            {apply?.signoff ? " · claims signoff (bug)" : " · does not claim signoff"}
            {apply?.repaired === false ? " · did not close timing" : ""}
            {apply?.leftover ? ` · leftover ${apply.leftover}` : ""}
            {apply?.rewrote?.length ? ` · wrote ${apply.rewrote.join("+")}` : ""}
          </em>
          {onRun ? (
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={() => onRun("eco_apply", true)}
            >
              {busy === "eco_apply" ? "Applying…" : "Run apply on eco_scratch"}
            </button>
          ) : null}
        </li>
        <li data-state={closeState(close)}>
          <span>3 · Close on copy</span>
          <b>
            {close
              ? `${close.summary ?? "signoff_all"}${close.ok ? " · educational ok" : " · not ok"}`
              : "signoff_all not run on eco_scratch"}
          </b>
          <em>
            FLOW_VARIANT=eco_scratch ./learn/scripts/run_signoff_all.sh
            {closePillars ? ` · ${closePillars}` : ""}
            {close?.setup_leftover?.setup_open
              ? close.setup_leftover.wns_kind === "output"
                ? ` · leftover setup open (WNS ${close.setup_leftover.wns_ns} at ${close.setup_leftover.clock_ns ?? 0.46} ns; register-to-register MET, leftover is course output delay)`
                : ` · leftover setup open (WNS ${close.setup_leftover.wns_ns} at ${close.setup_leftover.clock_ns ?? 0.46} ns)`
              : ""}
            {close?.leftover?.must_connect
              ? ` · leftover must-connect ${close.leftover.must_connect}${
                  close.leftover.circuits?.length
                    ? ` (${close.leftover.circuits.join(", ")})`
                    : ""
                }`
              : ""}
          </em>
          {onRun ? (
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={() => onRun("eco_close", true)}
            >
              {busy === "eco_close" ? "Closing…" : "Run signoff_all on copy"}
            </button>
          ) : null}
        </li>
      </ol>
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

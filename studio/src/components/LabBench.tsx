"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";

type Check = {
  id: string;
  design: string;
  ok: boolean;
  status: string;
  quantity: string;
  value: unknown;
  bound: string;
  note: string;
};

type Pair = {
  design: string;
  clockNs: number;
  verdict: string;
  versus: "base" | "previous";
  base: { id: string; variant?: string; wnsNs: number | null; irMv: number | null; area: number | null; power: number | null };
  cook: { id: string; variant?: string; wnsNs: number | null; irMv: number | null; area: number | null; power: number | null };
  delta: { wnsPs: number | null; areaPct: number | null; powerPct: number | null; irPct: number | null };
};

type LabSnap = {
  title: string;
  lead: string;
  goldMv: number;
  currentMv: number;
  physics: {
    ok: boolean;
    nReady: number;
    nChecks: number;
    watch: string[];
    fail: string[];
    checks: Check[];
    note?: string;
  } | null;
  staIr: {
    slackNs: number | null;
    slackIrNs: number | null;
    nJoined: number | null;
    nGates: number | null;
    degradationPs: number | null;
  };
  comparisons: Pair[];
  dse: { ok: boolean; summary: string; nCandidates: number } | null;
};

function fmt(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(v < 1 && v > -1 ? 4 : 3);
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    if ("slack_ns" in o) return `${fmt(o.slack_ns)} → ${fmt(o.slack_ir_ns)}`;
    if ("ir_mv" in o) return `${fmt(o.ir_mv)} mV`;
    if ("static_mv" in o) return `${fmt(o.static_mv)} / ${fmt(o.dynamic_mv)} mV`;
    if ("reconstructed_ns" in o) return `${fmt(Number(o.reconstructed_ns) * 1e3)} ps`;
  }
  return String(v);
}

function signed(v: number | null, unit: string): string {
  if (v == null || Number.isNaN(v)) return "—";
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(Math.abs(v) < 10 ? 2 : 1)}${unit}`;
}

export function LabBench({
  tone = "paper",
  onRun,
  busy,
}: {
  tone?: "paper" | "dark";
  onRun?: (action: string, long: boolean) => void;
  busy?: string | null;
}) {
  const [data, setData] = useState<LabSnap | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>("sta_ir_path");

  const refresh = useCallback(async () => {
    try {
      const r = await fetch("/api/lab", { cache: "no-store" });
      if (!r.ok) throw new Error(`lab ${r.status}`);
      setData((await r.json()) as LabSnap);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "lab error");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, busy]);

  const latest = data?.comparisons.filter((p) => p.versus === "base") ?? [];
  const previous = data?.comparisons.filter((p) => p.versus === "previous") ?? [];

  return (
    <section className={clsx("lb-bench", tone === "dark" && "lb-bench-dark")} aria-label="Lab bench">
      <header className="lb-mast">
        <div>
          <p className="lb-kicker">Field notes · not a brochure</p>
          <h2>What the numbers are allowed to mean</h2>
          <p className="lb-lead">
            {data?.lead ?? "Rail-scale checks on real finishes. Gold 45.298 mV stays a sentinel."}
          </p>
        </div>
        <div className="lb-rail-nums" aria-hidden>
          <span>
            gold <em>{data?.goldMv ?? 45.298}</em>
          </span>
          <span>
            live <em>{data?.currentMv ?? 6.075}</em>
          </span>
        </div>
      </header>

      {err && <p className="lb-err">{err}</p>}

      <div className="lb-split">
        <div className="lb-col">
          <h3>Physics ledger</h3>
          <p className="lb-sub">
            {data?.physics
              ? `${data.physics.nReady}/${data.physics.nChecks} ready · ${data.physics.watch.length} watch`
              : "Run validate_lab_physics.py"}
          </p>
          <ol className="lb-ledger">
            {(data?.physics?.checks ?? []).map((c) => (
              <li key={c.id} className={clsx("lb-row", `is-${c.status.toLowerCase()}`, open === c.id && "is-open")}>
                <button type="button" onClick={() => setOpen(open === c.id ? null : c.id)}>
                  <i>{c.status}</i>
                  <strong>{c.quantity}</strong>
                  <b>{fmt(c.value)}</b>
                </button>
                {open === c.id && (
                  <p>
                    {c.note} <em>{c.bound}</em>
                    {c.design !== "gcd" ? ` · ${c.design}` : ""}
                  </p>
                )}
              </li>
            ))}
          </ol>
        </div>

        <div className="lb-col">
          <h3>STA IR-aware</h3>
          <p className="lb-sub">Worst max path × ITerm V. Nets unscaled.</p>
          <dl className="lb-sta">
            <div>
              <dt>OpenSTA</dt>
              <dd>{fmt(data?.staIr.slackNs)} ns</dd>
            </div>
            <div>
              <dt>IR slack</dt>
              <dd>{fmt(data?.staIr.slackIrNs)} ns</dd>
            </div>
            <div>
              <dt>Stretch</dt>
              <dd>{fmt(data?.staIr.degradationPs)} ps</dd>
            </div>
            <div>
              <dt>Joined</dt>
              <dd>
                {data?.staIr.nJoined ?? "—"}/{data?.staIr.nGates ?? "—"}
              </dd>
            </div>
          </dl>
          <p className="lb-foot">
            Extra delay is Σ(delay_ir − delay). α = 1.3. Not Tempus.
          </p>

          <h3 className="lb-h-gap">Last cook vs slot base</h3>
          <p className="lb-sub">win_rule.py · same die · ±5 ps slack band</p>
          <table className="lb-cmp">
            <thead>
              <tr>
                <th>Slot</th>
                <th>Verdict</th>
                <th>ΔWNS</th>
                <th>ΔIR</th>
                <th>Δarea</th>
              </tr>
            </thead>
            <tbody>
              {latest.map((p) => (
                <tr key={`${p.design}-${p.versus}`} className={`is-${p.verdict}`}>
                  <td>
                    {p.design}
                    <small>{p.clockNs} ns</small>
                  </td>
                  <td>{p.verdict}</td>
                  <td>{signed(p.delta.wnsPs, " ps")}</td>
                  <td>{signed(p.delta.irPct, "%")}</td>
                  <td>{signed(p.delta.areaPct, "%")}</td>
                </tr>
              ))}
              {!latest.length && (
                <tr>
                  <td colSpan={5}>No finished cooks to compare.</td>
                </tr>
              )}
            </tbody>
          </table>

          {previous.length > 0 && (
            <>
              <h3 className="lb-h-gap">This launch vs the cook before it</h3>
              <ul className="lb-prev">
                {previous.map((p) => (
                  <li key={`${p.design}-prev`}>
                    <span>
                      {p.design} · {p.verdict}
                    </span>
                    <span>{signed(p.delta.wnsPs, " ps")}</span>
                    <span>{signed(p.delta.irPct, "% IR")}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>

      <footer className="lb-actions">
        <Link href="/lab">Open the full bench</Link>
        {onRun && (
          <button type="button" disabled={Boolean(busy)} onClick={() => onRun("dse", false)}>
            {busy === "dse" ? "Cooking…" : "Launch DSE · then re-read the ledger"}
          </button>
        )}
      </footer>
    </section>
  );
}

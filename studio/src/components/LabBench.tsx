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

type Shot = {
  role: string;
  variant: string;
  designId: string;
  createdAt: number | null;
  nCandidates: number | null;
  nF4: number | null;
  winningIrMv: number | null;
  winningStaticMv: number | null;
  champAmgMv: number | null;
  champWnsNs: number | null;
  spentS: number | null;
  summary: string;
  compare: {
    versus: number | null;
    sameMesh: boolean | null;
    note: string;
    delta: {
      n_candidates: number | null;
      winning_ir_pdn_mv: number | null;
      winning_static_mv: number | null;
      ir_cell_champ_wns_ns: number | null;
      spent_s: number | null;
    } | null;
  } | null;
};

type LabSnap = {
  title: string;
  lead: string;
  goldMv: number;
  currentMv: number | null;
  physics: {
    ok: boolean;
    nReady: number;
    nChecks: number;
    watch: string[];
    fail: string[];
    gap?: string[];
    checks: Check[];
    note?: string;
  } | null;
  staIr: {
    slackNs: number | null;
    slackIrNs: number | null;
    nJoined: number | null;
    nGates: number | null;
    degradationPs: number | null;
    worstCellIrMv?: number | null;
    map?: string | null;
  };
  comparisons: Pair[];
  dse: { ok: boolean; summary: string; nCandidates: number } | null;
  launches?: Shot[];
  thisLaunch?: Shot | null;
  prevLaunch?: Shot | null;
  asap7?: {
    ok: boolean;
    variant: string | null;
    design: string | null;
    corner: string | null;
    vt: string[];
    libModel: string | null;
    track: string | null;
    gds: string | null;
    productWin: boolean;
    comparableToGoldIr: boolean;
    goldIrMv: number;
    leftover: Record<string, unknown> | null;
    qor: { wns?: unknown; tns?: unknown; area?: unknown; power?: unknown } | null;
    note: string | null;
  } | null;
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

function shotWhen(ts: number | null): string {
  if (ts == null) return "undated";
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return "undated";
  return d.toISOString().replace("T", " ").slice(0, 16);
}

function ShotFace({ shot, label }: { shot: Shot | null; label: string }) {
  return (
    <article className="lb-face">
      <header>
        <span>{label}</span>
        <strong>{shot ? `${shot.role} · ${shot.designId}` : "no cook yet"}</strong>
      </header>
      <dl>
        <div>
          <dt>Winning IR</dt>
          <dd>{shot?.winningIrMv != null ? `${shot.winningIrMv.toFixed(3)} mV` : "—"}</dd>
        </div>
        <div>
          <dt>Static</dt>
          <dd>{shot?.winningStaticMv != null ? `${shot.winningStaticMv.toFixed(3)} mV` : "—"}</dd>
        </div>
        <div>
          <dt>AMG champ</dt>
          <dd>{shot?.champAmgMv != null ? `${shot.champAmgMv.toFixed(3)} mV` : "—"}</dd>
        </div>
        <div>
          <dt>IR-cell WNS</dt>
          <dd>{shot?.champWnsNs != null ? `${shot.champWnsNs.toFixed(3)} ns` : "—"}</dd>
        </div>
        <div>
          <dt>Candidates</dt>
          <dd>{shot?.nCandidates ?? "—"}</dd>
        </div>
        <div>
          <dt>F4</dt>
          <dd>{shot?.nF4 ?? "—"}</dd>
        </div>
      </dl>
      <p>{shot ? shotWhen(shot.createdAt) : "Launch DSE to stamp a shot."}</p>
    </article>
  );
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

  const launches = data?.launches ?? [];
  const nGap = data?.physics?.gap?.length ?? 0;
  const folio = `${data?.physics?.nReady ?? "–"}/${data?.physics?.nChecks ?? "–"}`;

  return (
    <section className={clsx("lb-bench", tone === "dark" && "lb-bench-dark")} aria-label="Lab bench">
      <header className="lb-mast">
        <div>
          <p className="lb-kicker">Lab physics {folio}</p>
          <h2>Rail-scale checks on finished cooks</h2>
          <p className="lb-lead">
            {data?.lead ?? "Rail-scale checks on real finishes. Gold 45.298 mV stays a sentinel."}
          </p>
        </div>
        <div className="lb-rail-nums" aria-hidden>
          <span>
            gold <em>{data?.goldMv ?? 45.298}</em>
          </span>
          <span>
            current_run <em>{data?.currentMv != null ? data.currentMv.toFixed(3) : "—"}</em>
          </span>
        </div>
      </header>

      {err && <p className="lb-err">{err}</p>}

      <article className="lb-face" id="asap7" aria-label="ASAP7 lab track">
        <header>
          <span>ASAP7 lab</span>
          <strong>{data?.asap7?.variant ?? "no lab_asap7 cook yet"}</strong>
        </header>
        <dl>
          <div>
            <dt>Corner / VT / lib</dt>
            <dd>
              {data?.asap7
                ? `${data.asap7.corner ?? "—"} · ${(data.asap7.vt ?? []).join("+") || "—"} · ${data.asap7.libModel ?? "—"}`
                : "—"}
            </dd>
          </div>
          <div>
            <dt>GDS</dt>
            <dd>{data?.asap7?.ok ? "yes" : "not cooked"}</dd>
          </div>
          <div>
            <dt>Product win</dt>
            <dd>no</dd>
          </div>
          <div>
            <dt>vs gold 45.298</dt>
            <dd>not comparable</dd>
          </div>
        </dl>
        <p>{data?.asap7?.note ?? "Predictive FinFET track. Cook with ./scripts/run_lab_asap7.sh"}</p>
      </article>

      <div id="dse-compare" className="lb-faces">
        <ShotFace shot={data?.prevLaunch ?? null} label="Cook before" />
        <ShotFace shot={data?.thisLaunch ?? null} label="This launch" />
        <aside className="lb-delta">
          <h3>This launch vs the one before</h3>
          <p className="lb-sub">
            {data?.thisLaunch?.compare?.note ??
              "Every DSE cook appends a shot. ΔIR is not a product win across extracts."}
          </p>
          <ul>
            <li>
              <span>Δ candidates</span>
              <b>{signed(data?.thisLaunch?.compare?.delta?.n_candidates ?? null, "")}</b>
            </li>
            <li>
              <span>Δ winning IR</span>
              <b>{signed(data?.thisLaunch?.compare?.delta?.winning_ir_pdn_mv ?? null, " mV")}</b>
            </li>
            <li>
              <span>Δ static</span>
              <b>{signed(data?.thisLaunch?.compare?.delta?.winning_static_mv ?? null, " mV")}</b>
            </li>
            <li>
              <span>Δ IR-cell WNS</span>
              <b>{signed(data?.thisLaunch?.compare?.delta?.ir_cell_champ_wns_ns ?? null, " ns")}</b>
            </li>
          </ul>
          {launches.length > 0 && (
            <ol className="lb-tape">
              {launches
                .slice(-6)
                .reverse()
                .map((s, i) => (
                  <li key={`${s.createdAt}-${i}`}>
                    <i>{s.role}</i>
                    <span>{s.winningIrMv != null ? `${s.winningIrMv.toFixed(2)} mV` : "—"}</span>
                    <em>{s.nCandidates ?? "—"} cand</em>
                  </li>
                ))}
            </ol>
          )}
        </aside>
      </div>

      <div className="lb-split">
        <div className="lb-col">
          <h3>Physics ledger</h3>
          <p className="lb-sub">
            {data?.physics
              ? `${data.physics.nReady}/${data.physics.nChecks} ready · ${data.physics.watch.length} watch · ${nGap} gap`
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
            <div>
              <dt>Worst cell</dt>
              <dd>
                {data?.staIr.worstCellIrMv != null
                  ? `${data.staIr.worstCellIrMv.toFixed(3)} mV`
                  : "—"}
              </dd>
            </div>
          </dl>
          {data?.staIr.map ? (
            <p className="lb-foot">
              current_run map <code>{data.staIr.map}</code>
            </p>
          ) : null}
          <p className="lb-foot">Extra delay is Σ(delay_ir − delay). α = 1.3. Not Tempus.</p>

          <h3 className="lb-h-gap">Product wins</h3>
          <p className="lb-sub">
            Official netlist, fixed die, area/power/leakage/IR together. Decided
            only on <Link href="/product">/product</Link> by{" "}
            <code>win_rule.py</code>. This bench does not host that table.
          </p>
        </div>
      </div>

      <footer className="lb-actions">
        <Link href="/lab">Open the full bench</Link>
        {onRun && (
          <button type="button" disabled={Boolean(busy)} onClick={() => onRun("dse", false)}>
            {busy === "dse" ? "Cooking…" : "Launch DSE · stamp a new shot"}
          </button>
        )}
      </footer>
    </section>
  );
}

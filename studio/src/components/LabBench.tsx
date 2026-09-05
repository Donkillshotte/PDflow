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
    clkPs?: number | null;
    gds: string | null;
    productWin: boolean;
    comparableToGoldIr: boolean;
    leftover: Record<string, unknown> | null;
    qor: {
      wnsPs: number | null;
      areaUm2: number | null;
      powerMw: number | null;
      leakageNw: number | null;
      irDropVddMv: number | null;
      periodMinPs: number | null;
      fmaxGhz: number | null;
      timingClosed: boolean;
    } | null;
    folio?: { variant?: string; wns_ps?: number | null; timing_closed?: boolean; fmax_ghz?: number | null }[];
    cookCount?: number;
    closedCount?: number;
    lvs?: { matchPct: number | null; nMatched: number | null; nLogic: number | null; calibre: boolean; closed: boolean } | null;
    mmmc?: { setupWnsPs: number | null; holdWnsPs: number | null; ok: boolean } | null;
    pdk?: {
      ok: boolean;
      nPm: number | null;
      nModel: number | null;
      corners: string[];
      calibreReady: boolean;
      calibrePlaceholder: boolean;
      drm: boolean;
      cdslib: boolean;
    } | null;
    spice?: {
      ok: boolean;
      patch: string | null;
      inverted: boolean;
      voutWhenVinHigh: number | null;
      voutWhenVinLow: number | null;
    } | null;
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
        <strong>{shot ? `${shot.role} · ${shot.designId}` : "no run yet"}</strong>
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
            <dt>WNS</dt>
            <dd>
              {data?.asap7?.qor?.wnsPs != null
                ? `${data.asap7.qor.wnsPs.toFixed(1)} ps${data.asap7.qor.timingClosed ? " · closed" : " · open"}`
                : "—"}
            </dd>
          </div>
          <div>
            <dt>Area</dt>
            <dd>{data?.asap7?.qor?.areaUm2 != null ? `${data.asap7.qor.areaUm2.toFixed(1)} µm²` : "—"}</dd>
          </div>
          <div>
            <dt>Power</dt>
            <dd>{data?.asap7?.qor?.powerMw != null ? `${data.asap7.qor.powerMw.toFixed(3)} mW` : "—"}</dd>
          </div>
          <div>
            <dt>Leakage</dt>
            <dd>{data?.asap7?.qor?.leakageNw != null ? `${data.asap7.qor.leakageNw.toFixed(1)} nW` : "—"}</dd>
          </div>
          <div>
            <dt>IR VDD</dt>
            <dd>
              {data?.asap7?.qor?.irDropVddMv != null ? `${data.asap7.qor.irDropVddMv.toFixed(2)} mV` : "—"}
            </dd>
          </div>
          <div>
            <dt>fmax / period_min</dt>
            <dd>
              {data?.asap7?.qor?.fmaxGhz != null
                ? `${data.asap7.qor.fmaxGhz.toFixed(2)} GHz · ${fmt(data.asap7.qor.periodMinPs)} ps`
                : "—"}
            </dd>
          </div>
          <div>
            <dt>Folio</dt>
            <dd>
              {data?.asap7?.cookCount ?? 0} cooks · {data?.asap7?.closedCount ?? 0} WNS≥0
            </dd>
          </div>
          <div>
            <dt>Product win</dt>
            <dd>no</dd>
          </div>
          <div>
            <dt>vs 45.298 mV</dt>
            <dd>not comparable</dd>
          </div>
          <div>
            <dt>LVS vs CDL</dt>
            <dd>
              {data?.asap7?.lvs
                ? `${data.asap7.lvs.matchPct ?? "—"}% · not Calibre`
                : "—"}
            </dd>
          </div>
          <div>
            <dt>Setup WC / hold BC</dt>
            <dd>
              {data?.asap7?.mmmc
                ? `${fmt(data.asap7.mmmc.setupWnsPs)} / ${fmt(data.asap7.mmmc.holdWnsPs)} ps`
                : "—"}
            </dd>
          </div>
          <div>
            <dt>Layer 1 PDK</dt>
            <dd>
              {data?.asap7?.pdk
                ? `${data.asap7.pdk.nPm ?? "—"} .pm · ${data.asap7.pdk.nModel ?? "—"} models · ${(data.asap7.pdk.corners ?? []).join("/") || "—"}`
                : "—"}
            </dd>
          </div>
          <div>
            <dt>Calibre decks</dt>
            <dd>
              {data?.asap7?.pdk
                ? data.asap7.pdk.calibreReady
                  ? "present · binary still required"
                  : "leftover Calibre · ASU encrypted tarball"
                : "—"}
            </dd>
          </div>
          <div>
            <dt>Xyce inverter</dt>
            <dd>
              {data?.asap7?.spice
                ? `${data.asap7.spice.patch ?? "level 72→107"}${data.asap7.spice.inverted ? " · inverted" : " · leftover"}`
                : "—"}
            </dd>
          </div>
        </dl>
        {(data?.asap7?.folio?.length ?? 0) > 0 && (
          <ol className="lb-tape" aria-label="ASAP7 live runs">
            {(data?.asap7?.folio ?? []).map((row, i) => (
              <li key={`${row.variant ?? "cook"}-${i}`}>
                <i>{row.timing_closed ? "closed" : "open"}</i>
                <span>{row.variant ?? "—"}</span>
                <em>
                  {row.wns_ps != null ? `${Number(row.wns_ps).toFixed(1)} ps` : "—"}
                  {row.fmax_ghz != null ? ` · ${Number(row.fmax_ghz).toFixed(2)} GHz` : ""}
                </em>
              </li>
            ))}
          </ol>
        )}
        <p>{data?.asap7?.note ?? "Predictive FinFET track. Cook with ./scripts/run_lab_asap7.sh"}</p>
      </article>

      <div id="dse-compare" className="lb-faces">
        <ShotFace shot={data?.prevLaunch ?? null} label="Previous run" />
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

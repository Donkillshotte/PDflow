"use client";

import { useCallback, useEffect, useState } from "react";

type Hottest = { node?: string; ir_mv?: number; x?: number; y?: number };
type Window = { t_start_ns?: number; t_end_ns?: number; t_peak_ns?: number; i_peak_a?: number };
type Level = { status?: string; mode?: string; note?: string; reason?: string; windows?: Window[] };
type PipelineStep = { id: number; name: string; status: string; via: string };
type StatusChip = { status?: string };
type Scenario = { mode?: string; droop_mv?: number; t_ns?: number; primary?: boolean };
type Timing = { status?: string; degradation_ps?: number; scale?: number };
type Amg = {
  ok?: boolean;
  worst_droop_mv?: number;
  abs_err_vs_A_mv?: number;
  n_levels?: number;
};
type DynReport = {
  ok?: boolean;
  summary?: string;
  mode?: string;
  vdd?: number;
  dynamic?: { worst_droop?: number; worst_droop_pct?: number; worst_time_s?: number };
  static?: { worst_ir?: number };
  heatmap?: { taps?: number; ir_max_mv?: number; hottest?: Hottest[] };
  ngspice_gold?: { ok?: boolean; abs_err_mv?: number } | null;
  sim_levels?: {
    L0_static?: Level;
    L1_vectorless_dynamic?: Level;
    L2_vcd_dynamic?: Level;
    L3_windowed?: Level;
  };
  pipeline?: PipelineStep[];
  emsim_split?: {
    A_cell_current?: { status?: string; pwl_sources?: number };
    B_pdn_solve?: { status?: string; solver?: string };
  };
  hotspot?: {
    node?: string;
    t_ns?: number;
    droop_mv?: number;
    vmin?: number;
    contributors?: { seq_frac?: number; combo_frac?: number };
  };
  platform?: {
    solvers?: {
      A_direct_be?: StatusChip;
      B_sa_amg?: StatusChip;
      C_rational_krylov_mor?: StatusChip;
    };
    network_levels?: {
      N1_R?: StatusChip;
      N2_RC?: StatusChip;
      N3_RC_pkg?: StatusChip;
      N4_vrm?: StatusChip;
    };
    product_tiers?: {
      FAST?: StatusChip;
      ACCURATE?: StatusChip;
      SIGNOFF?: StatusChip;
    };
    timing_impact?: Timing;
  };
  solver_b?: Amg;
  scenarios?: Scenario[];
  timing_impact?: Timing;
};

function ChipList({
  label,
  items,
}: {
  label: string;
  items: { key: string; status?: string; text: string }[];
}) {
  return (
    <div className="fl-dynir-group">
      <span>{label}</span>
      <ul className="fl-dynir-levels" aria-label={label}>
        {items.map((it) => (
          <li key={it.key} data-status={it.status ?? "GAP"}>
            {it.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DynamicIrHeatmap({
  variant = "flowlab",
}: {
  variant?: string;
}) {
  const [report, setReport] = useState<DynReport | null>(null);
  const [missing, setMissing] = useState(false);

  const load = useCallback(async () => {
    const res = await fetch(
      `/api/content?path=sim/reports/dynamic_ir_${variant}.json`,
    );
    if (!res.ok) {
      setMissing(true);
      setReport(null);
      return;
    }
    const body = (await res.json()) as { content?: string };
    try {
      setReport(JSON.parse(body.content ?? "") as DynReport);
      setMissing(false);
    } catch {
      setMissing(true);
      setReport(null);
    }
  }, [variant]);

  useEffect(() => {
    void load();
  }, [load]);

  const droopMv = (report?.dynamic?.worst_droop ?? 0) * 1e3;
  const staticMv = (report?.static?.worst_ir ?? 0) * 1e3;
  const tNs = (report?.dynamic?.worst_time_s ?? 0) * 1e9;
  const gold = report?.ngspice_gold;
  const svgSrc = `/api/content?path=sim/reports/dynamic_ir_${variant}.svg`;
  const levels = report?.sim_levels;
  const win = levels?.L3_windowed?.windows?.[0];
  const contrib = report?.hotspot?.contributors;
  const seqPct = ((contrib?.seq_frac ?? 0) * 100).toFixed(0);
  const comboPct = ((contrib?.combo_frac ?? 0) * 100).toFixed(0);
  const plat = report?.platform;
  const solvers = plat?.solvers;
  const nets = plat?.network_levels;
  const tiers = plat?.product_tiers;
  const amg = report?.solver_b;
  const timing = report?.timing_impact ?? plat?.timing_impact;
  const scenarios = report?.scenarios ?? [];
  const worstScen = scenarios[0];

  return (
    <section className="fl-dynir" aria-label="Dynamic IR heatmap">
      <header className="fl-dynir-head">
        <strong>Dynamic IR · I(t) per pin</strong>
        <p>
          Piattaforma ibrida: OpenROAD frontend · Solver A golden · Solver B
          SA-AMG · C = stessa A, molti I(t) · vyges = bootstrap ·{" "}
          <a href="/materiali/reference/dynamic-ir.md">dynamic-ir</a>
          {" · "}
          <a href="/materiali/reference/dynamic-ir-landscape.md">landscape</a>
        </p>
      </header>
      {missing || !report?.ok ? (
        <p className="fl-dynir-empty">
          Report assente — esegui l’azione <code>dynamic_ir</code> dopo finish.
        </p>
      ) : (
        <>
          <p className="fl-dynir-summary">{report.summary}</p>
          <dl className="fl-dynir-gauges">
            <div>
              <dt>Static IR</dt>
              <dd>{staticMv.toFixed(2)} mV</dd>
            </div>
            <div>
              <dt>Dynamic droop</dt>
              <dd>
                {droopMv.toFixed(2)} mV
                {report.dynamic?.worst_droop_pct != null
                  ? ` (${report.dynamic.worst_droop_pct.toFixed(2)}%)`
                  : ""}
              </dd>
            </div>
            <div>
              <dt>t_worst</dt>
              <dd>{tNs.toFixed(2)} ns</dd>
            </div>
            <div>
              <dt>Modo</dt>
              <dd>{report.mode ?? "—"}</dd>
            </div>
            <div>
              <dt>ngspice gold</dt>
              <dd>
                {gold == null
                  ? "n/d"
                  : gold.ok
                    ? `PASS · ${gold.abs_err_mv?.toFixed(2) ?? "?"} mV`
                    : `CHECK · ${gold.abs_err_mv?.toFixed(2) ?? "?"} mV`}
              </dd>
            </div>
            {amg && (
              <div>
                <dt>|A−B| AMG</dt>
                <dd>
                  {(amg.abs_err_vs_A_mv ?? 0) < 0.001
                    ? "< 1 µV"
                    : `${(amg.abs_err_vs_A_mv ?? 0).toFixed(3)} mV`}
                  {amg.n_levels != null ? ` · L${amg.n_levels}` : ""}
                </dd>
              </div>
            )}
            {timing?.degradation_ps != null && (
              <div>
                <dt>Delay scale</dt>
                <dd>+{timing.degradation_ps.toFixed(2)} ps</dd>
              </div>
            )}
          </dl>
          {solvers && (
            <ChipList
              label="Solver (A gold · B workhorse · C shared A)"
              items={[
                {
                  key: "A",
                  status: solvers.A_direct_be?.status,
                  text: "A BE golden",
                },
                {
                  key: "B",
                  status: solvers.B_sa_amg?.status,
                  text: "B SA-AMG",
                },
                {
                  key: "C",
                  status: solvers.C_rational_krylov_mor?.status,
                  text: "C shared PDN",
                },
              ]}
            />
          )}
          {tiers && (
            <ChipList
              label="Livelli prodotto"
              items={[
                { key: "FAST", status: tiers.FAST?.status, text: "FAST" },
                {
                  key: "ACCURATE",
                  status: tiers.ACCURATE?.status,
                  text: "ACCURATE",
                },
                {
                  key: "SIGNOFF",
                  status: tiers.SIGNOFF?.status,
                  text: "SIGNOFF",
                },
              ]}
            />
          )}
          {nets && (
            <ChipList
              label="Rete R → VRM"
              items={[
                { key: "N1", status: nets.N1_R?.status, text: "N1 R" },
                { key: "N2", status: nets.N2_RC?.status, text: "N2 RC" },
                {
                  key: "N3",
                  status: nets.N3_RC_pkg?.status,
                  text: "N3 RC+pkg",
                },
                { key: "N4", status: nets.N4_vrm?.status, text: "N4 VRM" },
              ]}
            />
          )}
          {report.emsim_split && (
            <ChipList
              label="Split EMSim A/B"
              items={[
                {
                  key: "A",
                  status: report.emsim_split.A_cell_current?.status,
                  text: `A I(t) ${report.emsim_split.A_cell_current?.pwl_sources ?? "—"} PWL`,
                },
                {
                  key: "B",
                  status: report.emsim_split.B_pdn_solve?.status,
                  text: "B PDN A+B",
                },
              ]}
            />
          )}
          {levels && (
            <ChipList
              label="Sim L0–L3"
              items={[
                {
                  key: "L0",
                  status: levels.L0_static?.status,
                  text: "L0 static",
                },
                {
                  key: "L1",
                  status: levels.L1_vectorless_dynamic?.status,
                  text: `L1 ${report.mode ?? "synth"}`,
                },
                {
                  key: "L2",
                  status: levels.L2_vcd_dynamic?.status,
                  text: "L2 VCD",
                },
                {
                  key: "L3",
                  status: levels.L3_windowed?.status,
                  text:
                    win?.t_peak_ns != null
                      ? `L3 window ${win.t_peak_ns.toFixed(2)} ns`
                      : "L3 window",
                },
              ]}
            />
          )}
          {report.hotspot && (
            <p className="fl-dynir-hotspot">
              Hotspot {report.hotspot.node ?? "—"} · {report.hotspot.droop_mv?.toFixed(2)} mV @{" "}
              {report.hotspot.t_ns?.toFixed(2)} ns · I seq {seqPct}% / combo {comboPct}%
              {timing?.degradation_ps != null
                ? ` · delay +${timing.degradation_ps.toFixed(2)} ps`
                : ""}
            </p>
          )}
          {scenarios.length > 0 && (
            <ol className="fl-dynir-scenarios" aria-label="Scenario ranking">
              {scenarios.map((s) => (
                <li key={s.mode} data-primary={s.primary ? "1" : "0"}>
                  {s.mode}
                  {s.primary ? " (run)" : ""} · {s.droop_mv?.toFixed(2)} mV @{" "}
                  {s.t_ns?.toFixed(2)} ns
                </li>
              ))}
            </ol>
          )}
          {worstScen && !worstScen.primary && (
            <p className="fl-dynir-hotspot">
              Ranking: il peggiore è {worstScen.mode} ({worstScen.droop_mv?.toFixed(2)} mV),
              non il modo corrente.
            </p>
          )}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            className="fl-dynir-svg"
            src={svgSrc}
            alt={`Heatmap dynamic IR ${variant} all’istante di droop massimo`}
          />
        </>
      )}
    </section>
  );
}

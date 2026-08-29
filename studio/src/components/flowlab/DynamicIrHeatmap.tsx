"use client";

import { useCallback, useEffect, useState } from "react";

type Hottest = { node?: string; ir_mv?: number; x?: number; y?: number };
type Window = { t_start_ns?: number; t_end_ns?: number; t_peak_ns?: number; i_peak_a?: number };
type Level = {
  status?: string;
  mode?: string;
  note?: string;
  reason?: string;
  kind?: string;
  windows?: Window[];
  n_windows?: number;
  abs_err_vs_A_mv?: number;
  collapsed_to_full?: boolean;
};
type Activity = {
  status?: string;
  note?: string;
  sta?: {
    status?: string;
    n_applied?: number;
    n_inst?: number;
    worst_path?: { slack_ns?: number; n_gates?: number; startpoint?: string };
  };
  vcd?: { status?: string; n_matched?: number; kind?: string; n_applied?: number };
  saif?: { status?: string; n_matched?: number; n_idle?: number; n_joined?: number; kind?: string };
};
type PipelineStep = { id: number; name: string; status: string; via: string };
type StatusChip = { status?: string };
type Scenario = { mode?: string; droop_mv?: number; t_ns?: number; primary?: boolean };
type TimingPath = {
  status?: string;
  startpoint?: string;
  endpoint?: string;
  slack_ns?: number;
  slack_ir_ns?: number;
  n_gates?: number;
  n_joined?: number;
  gate_delay_ns?: number;
  gate_delay_ir_ns?: number;
};
type Timing = {
  status?: string;
  degradation_ps?: number;
  scale?: number;
  delay_nom_ps?: number;
  path?: TimingPath;
};
type Em = {
  status?: string;
  i_absmax_a?: number;
  j_absmax_a_m2?: number;
  dT_absmax_k?: number;
  ttf_rel_min?: number | null;
  n_with_j?: number;
  r_scale_hot?: number;
  rT_delta_ir_mv?: number;
  hottest?: { i_abs?: number };
  hottest_j?: { j_a_m2?: number; layer?: string };
};
type Ras = {
  ok?: boolean;
  worst_droop_mv?: number;
  abs_err_vs_A_mv?: number;
  n_levels?: number;
  backend?: string;
};
type Amg = {
  ok?: boolean;
  worst_droop_mv?: number;
  abs_err_vs_A_mv?: number;
  n_levels?: number;
  backend?: string;
};
type Mor = {
  ok?: boolean;
  worst_droop_mv?: number;
  abs_err_vs_A_mv?: number;
  m?: number;
  backend?: string;
};
type N4 = {
  ok?: boolean;
  worst_droop_mv?: number;
  abs_err_vs_N3_mv?: number;
  via?: string;
  backend?: string;
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
  ngspice_rl_gold?: { ok?: boolean; abs_err_mv?: number } | null;
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
    native_index_bits?: number | null;
    native_index?: StatusChip & { bits?: number | null };
    solvers?: {
      A_direct_be?: StatusChip;
      B_sa_amg?: StatusChip;
      C_rational_krylov_mor?: StatusChip;
      D_ras_schwarz?: StatusChip;
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
    em_thermal?: Em;
  };
  solver_b?: Amg;
  solver_c?: Mor;
  solver_d?: Ras;
  n4?: N4;
  scenarios?: Scenario[];
  timing_impact?: Timing;
  em?: Em;
  activity_model?: Activity;
  windowed?: { status?: string; abs_err_vs_A_mv?: number; n_windows?: number; steps?: number; full_steps?: number };
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
      { cache: "no-store" },
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
  const goldRl = report?.ngspice_rl_gold;
  const svgSrc = `/api/content?path=sim/reports/dynamic_ir_${variant}.svg`;
  const levels = report?.sim_levels;
  const win = levels?.L3_windowed?.windows?.[0];
  const contrib = report?.hotspot?.contributors;
  const seqPct = ((contrib?.seq_frac ?? 0) * 100).toFixed(0);
  const comboPct = ((contrib?.combo_frac ?? 0) * 100).toFixed(0);
  const plat = report?.platform;
  const em = report?.em ?? plat?.em_thermal;
  const solvers = plat?.solvers;
  const nets = plat?.network_levels;
  const tiers = plat?.product_tiers;
  const amg = report?.solver_b;
  const mor = report?.solver_c;
  const ras = report?.solver_d;
  const n4 = report?.n4;
  const timing = report?.timing_impact ?? plat?.timing_impact;
  const scenarios = report?.scenarios ?? [];
  const worstScen = scenarios[0];
  const sta = report?.activity_model?.sta;
  const vcd = report?.activity_model?.vcd;
  const saif = report?.activity_model?.saif;
  const l3 = levels?.L3_windowed;
  const pathT = timing?.path;

  return (
    <section className="fl-dynir" aria-label="Dynamic IR heatmap">
      <header className="fl-dynir-head">
        <strong>Dynamic IR · I(t) per pin</strong>
        <p>
          Piattaforma ibrida: OpenROAD frontend · Solver A golden · Solver B
          SA-AMG · C = Krylov MOR · D = RAS Schwarz · vyges = bootstrap ·{" "}
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
            {goldRl && (
              <div>
                <dt>ngspice R+L</dt>
                <dd>
                  {goldRl.ok
                    ? `PASS · ${goldRl.abs_err_mv?.toFixed(2) ?? "?"} mV`
                    : `CHECK · ${goldRl.abs_err_mv?.toFixed(2) ?? "?"} mV`}
                </dd>
              </div>
            )}
            {amg && (
              <div>
                <dt>|A−B| AMG</dt>
                <dd>
                  {(amg.abs_err_vs_A_mv ?? 0) < 0.001
                    ? "< 1 µV"
                    : `${(amg.abs_err_vs_A_mv ?? 0).toFixed(3)} mV`}
                  {amg.n_levels != null ? ` · L${amg.n_levels}` : ""}
                  {amg.backend ? ` · ${amg.backend}` : ""}
                </dd>
              </div>
            )}
            {mor && (
              <div>
                <dt>|A−C| MOR</dt>
                <dd>
                  {(mor.abs_err_vs_A_mv ?? 0) < 0.001
                    ? "< 1 µV"
                    : `${(mor.abs_err_vs_A_mv ?? 0).toFixed(3)} mV`}
                  {mor.m != null ? ` · m=${mor.m}` : ""}
                  {mor.backend ? ` · ${mor.backend}` : ""}
                </dd>
              </div>
            )}
            {ras && (
              <div>
                <dt>|A−D| RAS</dt>
                <dd>
                  {(ras.abs_err_vs_A_mv ?? 0) < 0.001
                    ? "< 1 µV"
                    : `${(ras.abs_err_vs_A_mv ?? 0).toFixed(3)} mV`}
                  {ras.n_levels != null ? ` · ndom=${ras.n_levels}` : ""}
                  {ras.backend ? ` · ${ras.backend}` : ""}
                </dd>
              </div>
            )}
            {n4 && (
              <div>
                <dt>|N3−N4| VRM</dt>
                <dd>
                  {(n4.abs_err_vs_N3_mv ?? 0) < 0.001
                    ? "< 1 µV"
                    : `${(n4.abs_err_vs_N3_mv ?? 0).toFixed(3)} mV`}
                  {n4.worst_droop_mv != null
                    ? ` · ${n4.worst_droop_mv.toFixed(2)} mV`
                    : ""}
                  {n4.backend ? ` · ${n4.backend}` : ""}
                </dd>
              </div>
            )}
            {em?.i_absmax_a != null && (
              <div>
                <dt>|I| branch</dt>
                <dd>
                  {(em.i_absmax_a * 1e3).toFixed(2)} mA
                  {em.status ? ` · ${em.status}` : ""}
                </dd>
              </div>
            )}
            {em?.n_with_j ? (
              <div>
                <dt>J max</dt>
                <dd>
                  {(em.j_absmax_a_m2 ?? 0).toExponential(2)} A/m²
                  {em.hottest_j?.layer ? ` · ${em.hottest_j.layer}` : ""}
                </dd>
              </div>
            ) : null}
            {em?.n_with_j ? (
              <div>
                <dt>ΔT lumped</dt>
                <dd>
                  {(em.dT_absmax_k ?? 0) < 1e-3
                    ? "< 1 mK"
                    : `${(em.dT_absmax_k ?? 0).toFixed(3)} K`}
                  {em.rT_delta_ir_mv != null
                    ? ` · ΔIR ${em.rT_delta_ir_mv.toFixed(4)} mV`
                    : ""}
                </dd>
              </div>
            ) : null}
            {em?.ttf_rel_min != null && em.n_with_j ? (
              <div>
                <dt>TTF_rel min</dt>
                <dd>{em.ttf_rel_min.toExponential(2)}</dd>
              </div>
            ) : null}
            {sta?.n_applied ? (
              <div>
                <dt>STA t50</dt>
                <dd>
                  {sta.n_applied}
                  {sta.n_inst != null ? ` / ${sta.n_inst} inst` : ""}
                  {sta.status ? ` · ${sta.status}` : ""}
                </dd>
              </div>
            ) : null}
            {vcd && vcd.kind === "vcd" ? (
              <div>
                <dt>VCD join</dt>
                <dd>
                  {vcd.status ?? "GAP"}
                  {vcd.n_matched != null ? ` · ${vcd.n_matched} names` : ""}
                </dd>
              </div>
            ) : null}
            {saif && (saif.kind === "saif" || (saif.n_joined ?? 0) > 0) ? (
              <div>
                <dt>SAIF join</dt>
                <dd>
                  {saif.status ?? "GAP"}
                  {saif.n_joined != null ? ` · ${saif.n_joined} inst` : ""}
                  {saif.n_idle ? ` · idle ${saif.n_idle}` : ""}
                </dd>
              </div>
            ) : null}
            {l3?.abs_err_vs_A_mv != null ? (
              <div>
                <dt>|A−W| L3</dt>
                <dd>
                  {l3.abs_err_vs_A_mv < 0.001
                    ? "< 1 µV"
                    : `${l3.abs_err_vs_A_mv.toFixed(3)} mV`}
                  {l3.n_windows != null ? ` · ${l3.n_windows} win` : ""}
                </dd>
              </div>
            ) : null}
            {plat?.native_index_bits != null ? (
              <div>
                <dt>Index</dt>
                <dd>
                  {plat.native_index_bits}-bit
                  {plat.native_index?.status ? ` · ${plat.native_index.status}` : ""}
                </dd>
              </div>
            ) : null}
            {timing?.degradation_ps != null && (
              <div>
                <dt>{pathT?.status === "READY" ? "Path delay" : "Delay scale"}</dt>
                <dd>
                  +{timing.degradation_ps.toFixed(2)} ps
                  {timing.status ? ` · ${timing.status}` : ""}
                </dd>
              </div>
            )}
            {pathT?.status === "READY" && pathT.slack_ns != null ? (
              <div>
                <dt>Path slack</dt>
                <dd>
                  {pathT.slack_ns.toFixed(4)} ns STA
                  {pathT.slack_ir_ns != null
                    ? ` · ${pathT.slack_ir_ns.toFixed(4)} ns IR`
                    : ""}
                  {pathT.n_joined != null ? ` · ${pathT.n_joined} gates` : ""}
                </dd>
              </div>
            ) : null}
          </dl>
          {solvers && (
            <ChipList
              label="Solver (A gold · B workhorse · C Krylov MOR · D RAS)"
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
                  text: "C Krylov RLC",
                },
                {
                  key: "D",
                  status: solvers.D_ras_schwarz?.status,
                  text: "D RAS Schwarz",
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
                  text: "N3 RC+pkg i_L",
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
                  text: `L1 ${sta?.n_applied ? "STA" : (report.mode ?? "synth")}`,
                },
                {
                  key: "L2",
                  status: levels.L2_vcd_dynamic?.status,
                  text: `L2 ${
                    levels.L2_vcd_dynamic?.kind === "saif"
                      ? "SAIF"
                      : levels.L2_vcd_dynamic?.kind === "fsdb"
                        ? "FSDB"
                        : "VCD"
                  }`,
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
                ? pathT?.status === "READY"
                  ? ` · path delay +${timing.degradation_ps.toFixed(2)} ps`
                  : ` · delay +${timing.degradation_ps.toFixed(2)} ps`
                : ""}
              {pathT?.status === "READY" && pathT.slack_ir_ns != null
                ? ` · slack IR ${pathT.slack_ir_ns.toFixed(3)} ns`
                : ""}
              {em?.hottest?.i_abs != null
                ? ` · |I| ${(em.hottest.i_abs * 1e3).toFixed(2)} mA`
                : ""}
              {em?.j_absmax_a_m2 != null && em.n_with_j
                ? ` · J ${em.j_absmax_a_m2.toExponential(2)} A/m²`
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

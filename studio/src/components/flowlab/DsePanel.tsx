"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Cand = {
  id: string;
  level: string;
  fidelity: string;
  status: string;
  knobs?: {
    name?: string;
    extract?: string;
    source?: string;
    catalog?: string;
    util?: number;
    extract_id?: string;
    host_source?: string;
    i_scale?: number;
  };
    qor?: {
    area_um2?: number | null;
    n_cells?: number | null;
    static_ir_mv?: number | null;
    dynamic_ir_mv?: number | null;
    congestion?: number | null;
    wns_cost?: number | null;
    tns_cost?: number | null;
    power_w?: number | null;
    leakage_w?: number | null;
    internal_power_w?: number | null;
    switching_power_w?: number | null;
    hpwl_um?: number | null;
    wirelength_um?: number | null;
    core_util?: number | null;
    em_j_a_m2?: number | null;
  };
  artifacts?: {
    hpwl?: number;
    hpwl_um?: number;
    overflow?: number;
    wns_ns?: number;
    n_r?: number;
    extract?: string;
  };
};
type Attr = { status?: string; modules?: string[]; scope?: string; droop_mv?: number };
type DseReport = {
  ok?: boolean;
  summary?: string;
  n_candidates?: number;
  n_f1?: number;
  n_arch?: number;
  n_f2_fast?: number;
  n_f2_gpl?: number;
  n_f2_gpl_catalog?: number;
  n_f2_region?: number;
  n_f4_region_extract?: number;
  n_f3?: number;
  n_f3_sdf?: number;
  n_f3_spef?: number;
  n_f5?: number;
  n_f2_grt?: number;
  n_f4?: number;
  n_f4_extract?: number;
  n_f4_host_extract?: number;
  n_f4_host_region_extract?: number;
  n_f4_amg?: number;
  n_f4_iscale?: number;
  n_f4_iscale_win?: number;
  n_f4_iscale_champ?: number;
  ir_cell_iscale_champ_mv?: number;
  ir_cell_iscale_champ_scale?: number;
  ir_cell_iscale_champ_vs_win_mv?: number;
  n_ir_cell?: number;
  n_ir_cell_champ?: number;
  ir_cell_champ_wns_ns?: number;
  ir_cell_champ_modules?: string;
  n_f4_ir_cell_champ_extract?: number;
  ir_cell_champ_extract_mv?: number;
  ir_cell_champ_extract_residual_mv?: number;
  n_ir_cell_champ_pdn?: number;
  ir_cell_champ_pdn_mv?: number;
  ir_cell_champ_pdn_name?: string;
  ir_cell_champ_pdn_vs_host_win_mv?: number;
  n_ir_cell_champ_cone?: number;
  ir_cell_champ_cone_wns_ns?: number;
  ir_cell_champ_cone_modules?: string;
  n_f4_ir_cell_champ_cone_extract?: number;
  ir_cell_champ_cone_extract_mv?: number;
  ir_cell_champ_cone_extract_residual_mv?: number;
  n_ir_cell_champ_cone_pdn?: number;
  ir_cell_champ_cone_pdn_mv?: number;
  ir_cell_champ_cone_pdn_name?: string;
  ir_cell_champ_cone_pdn_vs_host_win_mv?: number;
  n_f4_ir_cell_champ_cone_region_extract?: number;
  ir_cell_champ_cone_region_mv?: number;
  ir_cell_champ_cone_region_residual_mv?: number;
  ir_cell_champ_cone_region_bin?: string;
  n_ir_cell_champ_cone_region_pdn?: number;
  ir_cell_champ_cone_region_pdn_mv?: number;
  ir_cell_champ_cone_region_pdn_name?: string;
  ir_cell_champ_cone_region_pdn_vs_host_win_mv?: number;
  n_f4_amg_champ?: number;
  ir_champ_amg_mv?: number;
  ir_champ_amg_vs_direct_mv?: number;
  n_f4_ras_champ?: number;
  ir_champ_ras_mv?: number;
  ir_champ_ras_vs_direct_mv?: number;
  n_f4_krylov_champ?: number;
  ir_champ_krylov_mv?: number;
  ir_champ_krylov_vs_direct_mv?: number;
  winning_static_mv?: number;
  winning_static_extract?: string;
  n_static_ir_steer?: number;
  static_ir_steer_mv?: number;
  static_ir_steer_dyn_mv?: number;
  static_ir_steer_name?: string;
  static_ir_steer_vs_champ_mv?: number;
  n_static_mesh?: number;
  static_mesh_mv?: number;
  static_mesh_dyn_mv?: number;
  static_mesh_name?: string;
  static_mesh_vs_champ_mv?: number;
  n_static_straps?: number;
  static_straps_mv?: number;
  static_straps_dyn_mv?: number;
  static_straps_name?: string;
  static_straps_vs_champ_mv?: number;
  n_em_straps?: number;
  em_straps_j?: number;
  em_straps_name?: string;
  em_straps_vs_champ_j?: number;
  em_straps_vs_strap_j?: number;
  winning_em_j?: number;
  n_winning_ir_pdn?: number;
  winning_ir_pdn_mv?: number;
  winning_ir_pdn_name?: string;
  winning_ir_pdn_vs_champ_mv?: number;
  winning_ir_region_mv?: number;
  winning_ir_region_bin?: string;
  winning_ir_region_residual_mv?: number;
  n_f4_winning_ir_region_extract?: number;
  winning_ir_region_pdn_mv?: number;
  winning_ir_region_pdn_name?: string;
  winning_ir_region_pdn_vs_host_win_mv?: number;
  n_winning_ir_region_pdn?: number;
  winning_ir_region_cell_wns_ns?: number;
  winning_ir_region_cell_modules?: string;
  n_winning_ir_region_cell?: number;
  winning_ir_region_cell_extract_mv?: number;
  winning_ir_region_cell_extract_residual_mv?: number;
  n_f4_winning_ir_region_cell_extract?: number;
  winning_ir_region_cell_pdn_mv?: number;
  winning_ir_region_cell_pdn_name?: string;
  winning_ir_region_cell_pdn_vs_host_win_mv?: number;
  n_winning_ir_region_cell_pdn?: number;
  winning_ir_region_cell_leftover_wns_ns?: number;
  winning_ir_region_cell_leftover_modules?: string;
  n_winning_ir_region_cell_leftover?: number;
  winning_ir_region_cell_leftover_extract_mv?: number;
  winning_ir_region_cell_leftover_extract_residual_mv?: number;
  n_f4_winning_ir_region_cell_leftover_extract?: number;
  winning_ir_region_cell_leftover_pdn_mv?: number;
  winning_ir_region_cell_leftover_pdn_name?: string;
  winning_ir_region_cell_leftover_pdn_vs_host_win_mv?: number;
  n_winning_ir_region_cell_leftover_pdn?: number;
  winning_ir_region_cell_leftover2_wns_ns?: number;
  winning_ir_region_cell_leftover2_modules?: string;
  n_winning_ir_region_cell_leftover2?: number;
  winning_ir_region_cell_leftover2_extract_mv?: number;
  winning_ir_region_cell_leftover2_extract_residual_mv?: number;
  n_f4_winning_ir_region_cell_leftover2_extract?: number;
  winning_ir_region_cell_leftover2_pdn_mv?: number;
  winning_ir_region_cell_leftover2_pdn_name?: string;
  winning_ir_region_cell_leftover2_pdn_vs_host_win_mv?: number;
  n_winning_ir_region_cell_leftover2_pdn?: number;
  n_f4_ir_cell_extract?: number;
  n_ir_cell_pdn?: number;
  ir_cell_extract_mv?: number;
  ir_cell_extract_residual_mv?: number;
  ir_cell_pdn_mv?: number;
  ir_cell_pdn_name?: string;
  n_f4_ir_cell_region_extract?: number;
  ir_cell_region_mv?: number;
  ir_cell_region_residual_mv?: number;
  ir_cell_region_bin?: string;
  n_ir_cell_region_pdn?: number;
  ir_cell_region_pdn_mv?: number;
  ir_cell_region_pdn_name?: string;
  ir_cell_region_pdn_vs_host_win_mv?: number;
  n_host_ir_steer?: number;
  n_port_steer?: number;
  n_f4_solve?: number;
  surrogate_f1_to_f2_gnn?: { n?: number; uncertainty?: string; via?: string };
  pareto?: { logic?: string[]; architecture?: string[]; physical?: string[]; note?: string };
  pareto_gated?: { logic?: string[]; architecture?: string[]; physical?: string[]; note?: string };
  attribution?: Attr;
  focus?: { focus?: string; scope?: string };
  plan?: { steps?: { level?: string; reason?: string }[] };
  candidates?: Cand[];
  refine?: {
    depth?: number;
    label?: string;
    n_cells?: number;
    modules?: string | null;
    extract_mv?: number | null;
    pdn_mv?: number | null;
    catalog_mv?: number | null;
    leftover_n?: number;
  }[];
};

const LEVELS = ["architecture", "logic", "synthesis", "cell", "net", "physical", "routing", "pdn"] as const;

function irChips(report: DseReport): { k: string; v: string }[] {
  const chips: { k: string; v: string }[] = [];
  if (report.winning_ir_pdn_mv != null)
    chips.push({ k: "winning IR", v: `${report.winning_ir_pdn_mv.toFixed(3)} mV` });
  if (report.winning_static_mv != null)
    chips.push({ k: "static", v: `${report.winning_static_mv.toFixed(3)} mV` });
  if (report.ir_champ_amg_mv != null)
    chips.push({ k: "AMG", v: `${report.ir_champ_amg_mv.toFixed(3)} mV` });
  if (report.ir_champ_ras_mv != null)
    chips.push({ k: "RAS", v: `${report.ir_champ_ras_mv.toFixed(3)} mV` });
  if (report.ir_champ_krylov_mv != null)
    chips.push({ k: "Krylov", v: `${report.ir_champ_krylov_mv.toFixed(3)} mV` });
  if (report.ir_cell_champ_extract_mv != null)
    chips.push({ k: "IR-cell", v: `${report.ir_cell_champ_extract_mv.toFixed(3)} mV` });
  if (report.ir_cell_champ_wns_ns != null)
    chips.push({ k: "IR-cell WNS", v: `${report.ir_cell_champ_wns_ns.toFixed(3)} ns` });
  if (report.n_candidates != null) chips.push({ k: "candidates", v: String(report.n_candidates) });
  return chips;
}

function fmtMv(n?: number | null): string | null {
  return n != null ? `${n.toFixed(3)} mV` : null;
}

function fmtNs(n?: number | null): string | null {
  return n != null ? `${n >= 0 ? "+" : ""}${n.toFixed(3)} ns` : null;
}

function irTapeRows(report: DseReport): { k: string; v: string }[] {
  const rows: { k: string; v: string }[] = [];
  const add = (k: string, v: string | null | undefined) => {
    if (v) rows.push({ k, v });
  };
  add("winning IR", fmtMv(report.winning_ir_pdn_mv));
  add("static", fmtMv(report.winning_static_mv));
  add("AMG", fmtMv(report.ir_champ_amg_mv));
  add("RAS", fmtMv(report.ir_champ_ras_mv));
  add("Krylov", fmtMv(report.ir_champ_krylov_mv));
  add("IR-cell WNS", fmtNs(report.ir_cell_champ_wns_ns));
  add("IR-cell extract", fmtMv(report.ir_cell_champ_extract_mv));
  add("IR-cell PDN", fmtMv(report.ir_cell_champ_pdn_mv));
  add("IR cone WNS", fmtNs(report.ir_cell_champ_cone_wns_ns));
  add("IR cone extract", fmtMv(report.ir_cell_champ_cone_extract_mv));
  add("winning region", fmtMv(report.winning_ir_region_mv));
  if (report.em_straps_j != null) {
    add("EM straps", `${(report.em_straps_j / 1e9).toFixed(2)}e9 A/m²`);
  }
  if (report.refine?.length) {
    for (const fr of report.refine) {
      const mv = fr.catalog_mv ?? fr.pdn_mv ?? fr.extract_mv;
      add(fr.label ?? `refine[${fr.depth}]`, mv != null ? `${mv.toFixed(3)} mV` : `n=${fr.n_cells ?? "?"}`);
    }
  }
  return rows;
}

export function DsePanel() {
  const [report, setReport] = useState<DseReport | null>(null);

  const load = useCallback(async () => {
    const r = await fetch("/api/content?path=sim/reports/dse_flowlab.json", { cache: "no-store" });
    if (!r.ok) {
      setReport(null);
      return;
    }
    const body = await r.json();
    try {
      setReport(JSON.parse(body.content) as DseReport);
    } catch {
      setReport(null);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const cands = report?.candidates ?? [];
  const front = report?.pareto_gated ?? report?.pareto;
  const frontLogic = new Set(front?.logic ?? []);
  const frontArch = new Set(front?.architecture ?? []);

  return (
    <section className="fl-dynir" aria-label="DSE (proposer)">
      <header className="fl-dynir-head">
        <strong>DSE · proposer</strong>
        <p>
          Suggests knobs and extracts. Does not run <code>signoff_all</code>.{" "}
          <Link href="/materials/reference/dse.md">dse.md</Link>
        </p>
      </header>
      {!report?.ok ? (
        <p className="fl-dynir-empty">
          Report missing — run the <code>dse</code> (F5-lite, not <code>make finish</code>).
        </p>
      ) : (
        <>
          <p className="fl-dynir-summary">{report.summary}</p>
          <p className="muted">
            Lab extracts only. Not gold Dynamic IR 45.298 mV and not the
            signoff chip mesh. DSE does not run <code>signoff_all</code>.
          </p>
          {(irChips(report).length > 0 ||
            report.n_ir_cell ||
            report.n_ir_cell_champ ||
            report.winning_static_mv != null) && (
            <details className="lb-raw">
            <summary>Lab IR highlights / raw tape</summary>
          {irChips(report).length > 0 && (
            <ul className="lb-chips" aria-label="DSE IR highlights">
              {irChips(report).map((c) => (
                <li key={c.k}>
                  <span>{c.k}</span>
                  <b>{c.v}</b>
                </li>
              ))}
            </ul>
          )}
            {irTapeRows(report).length > 0 && (
              <table className="fl-dynir-table" aria-label="Lab IR tape">
                <thead>
                  <tr>
                    <th>Extract</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {irTapeRows(report).map((r) => (
                    <tr key={r.k}>
                      <td>{r.k}</td>
                      <td>{r.v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            </details>
          )}
          <ul className="fl-dynir-levels">
            {LEVELS.map((lv) => {
              const n = cands.filter((c) => c.level === lv).length;
              const status = n ? "READY" : "GAP";
              return (
                <li key={lv} data-status={status}>
                  {lv} · {n}
                </li>
              );
            })}
          </ul>
          <dl className="fl-dynir-gauges">
            <div>
              <dt>Candidates</dt>
              <dd>{report.n_candidates ?? 0}</dd>
            </div>
            <div>
              <dt>F1</dt>
              <dd>
                {report.n_f1 ?? 0}
                {report.n_arch != null ? ` · arch ${report.n_arch}` : ""}
              </dd>
            </div>
            <div>
              <dt>F2</dt>
              <dd>
                fast {report.n_f2_fast ?? 0}
                {report.n_f2_gpl != null ? ` · GPL ${report.n_f2_gpl}` : ""}
                {report.n_f2_gpl_catalog != null ? ` · cat ${report.n_f2_gpl_catalog}` : ""}
                {report.n_f2_region != null ? ` · reg ${report.n_f2_region}` : ""}
                {report.n_f2_grt != null ? ` · GRT ${report.n_f2_grt}` : ""}
                {report.n_f5 != null ? ` · F5 ${report.n_f5}` : ""}
              </dd>
            </div>
            <div>
              <dt>F3 STA</dt>
              <dd>
                {report.n_f3 ?? 0}
                {report.n_f3_sdf != null ? ` · SDF ${report.n_f3_sdf}` : ""}
                {report.n_f3_spef != null ? ` · SPEF ${report.n_f3_spef}` : ""}
                {report.n_ir_cell != null ? ` · IR-c ${report.n_ir_cell}` : ""}
                {report.n_ir_cell_champ != null ? ` · IR-cc ${report.n_ir_cell_champ}` : ""}
                {report.n_ir_cell_champ_cone != null ? ` · IR-cn ${report.n_ir_cell_champ_cone}` : ""}
              </dd>
            </div>
            <div>
              <dt>F4 IR</dt>
              <dd>
                {report.n_f4 ?? 0}
                {report.n_f4_extract != null ? ` · ext ${report.n_f4_extract}` : ""}
                {report.n_f4_host_extract != null ? ` · host ${report.n_f4_host_extract}` : ""}
                {report.n_f4_amg != null ? ` · AMG ${report.n_f4_amg}` : ""}
                {report.n_f4_solve != null ? ` · solve ${report.n_f4_solve}` : ""}
              </dd>
            </div>
            <div>
              <dt>Pareto logic</dt>
              <dd>{front?.logic?.length ?? 0}</dd>
            </div>
            <div>
              <dt>GNN</dt>
              <dd>
                {report.surrogate_f1_to_f2_gnn?.uncertainty ?? "—"}
                {report.surrogate_f1_to_f2_gnn?.n != null
                  ? ` · n=${report.surrogate_f1_to_f2_gnn.n}`
                  : ""}
              </dd>
            </div>
            <div>
              <dt>IR cone</dt>
              <dd>
                {(report.attribution?.modules ?? []).join(", ") || "—"}
                {report.focus?.scope ? ` · ${report.focus.scope}` : ""}
              </dd>
            </div>
          </dl>
          {report.plan?.steps?.length ? (
            <details className="fl-dynir-plan">
              <summary>Plan · {report.plan.steps.length} steps</summary>
              <ul className="fl-dynir-summary">
                {report.plan.steps.map((s, i) => (
                  <li key={`${s.level}-${i}`}>
                    {s.level}: {s.reason}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
          <LevelTable
            title="Architecture · extract e-graph"
            rows={cands.filter((c) => c.level === "architecture")}
            front={frontArch}
          />
          <LevelTable
            title="Logic · ABC sequences"
            rows={cands.filter((c) => c.level === "logic")}
            front={frontLogic}
          />
          <PhysicalTable
            rows={cands.filter(
              (c) =>
                c.knobs?.source === "f2_fast_netgraph" ||
                c.knobs?.source === "f2_openroad_gpl" ||
                c.knobs?.source === "f2_openroad_grt" ||
                c.knobs?.source === "f2_openroad_gpl_region" ||
                c.knobs?.source === "f5_openroad_drt_rcx" ||
                c.knobs?.source === "f3_opensta_spef" ||
                c.knobs?.source === "f2_fast_barycenter",
            )}
          />
          <PdnTable rows={cands.filter((c) => c.level === "pdn")} />
        </>
      )}
    </section>
  );
}

function LevelTable({
  title,
  rows,
  front,
}: {
  title: string;
  rows: Cand[];
  front: Set<string>;
}) {
  if (!rows.length) return null;
  return (
    <div className="fl-dynir-group">
      <span>{title}</span>
      <table className="fl-dynir-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>F</th>
            <th>Stdcell µm²</th>
            <th>Cells</th>
            <th>WNS</th>
            <th>TNS</th>
            <th>Leak</th>
            <th>P tot</th>
            <th>Status</th>
            <th>Pareto</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id} data-status={c.status}>
              <td>{c.knobs?.name ?? c.knobs?.extract ?? c.id}</td>
              <td>{c.fidelity}</td>
              <td>{c.qor?.area_um2 != null ? c.qor.area_um2.toFixed(3) : "—"}</td>
              <td>{c.qor?.n_cells != null ? String(c.qor.n_cells) : "—"}</td>
              <td>
                {c.qor?.wns_cost != null ? `${(-c.qor.wns_cost).toFixed(3)} ns` : "—"}
              </td>
              <td>
                {c.qor?.tns_cost != null ? `${(-c.qor.tns_cost).toFixed(3)} ns` : "—"}
              </td>
              <td>
                {c.qor?.leakage_w != null ? `${c.qor.leakage_w.toExponential(2)} W` : "—"}
              </td>
              <td>
                {c.qor?.power_w != null ? `${c.qor.power_w.toExponential(2)} W` : "—"}
              </td>
              <td>{c.status}</td>
              <td>{front.has(c.id) ? "yes" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PhysicalTable({ rows }: { rows: Cand[] }) {
  if (!rows.length) return null;
  return (
    <div className="fl-dynir-group">
      <span>Physical / routing · F2-fast / GPL / GRT / F5-lite SPEF (not IR)</span>
      <table className="fl-dynir-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>F</th>
            <th>HPWL</th>
            <th>WNS</th>
            <th>TNS</th>
            <th>Leak</th>
            <th>Cong</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id} data-status={c.status}>
              <td>
                {c.knobs?.catalog
                  ? `${c.knobs.source ?? "gpl"} · ${c.knobs.catalog}`
                  : (c.knobs?.source ?? c.id)}
              </td>
              <td>{c.fidelity}</td>
              <td>
                {c.qor?.hpwl_um != null
                  ? `${c.qor.hpwl_um.toFixed(1)} µm`
                  : c.artifacts?.hpwl_um != null
                    ? `${c.artifacts.hpwl_um.toFixed(1)} µm`
                    : c.artifacts?.hpwl != null
                      ? c.artifacts.hpwl.toFixed(1)
                      : "—"}
              </td>
              <td>
                {c.artifacts?.wns_ns != null
                  ? `${c.artifacts.wns_ns.toFixed(3)} ns`
                  : c.qor?.wns_cost != null
                    ? `${(-c.qor.wns_cost).toFixed(3)} ns`
                    : "—"}
              </td>
              <td>
                {c.qor?.tns_cost != null ? `${(-c.qor.tns_cost).toFixed(3)} ns` : "—"}
              </td>
              <td>
                {c.qor?.leakage_w != null ? `${c.qor.leakage_w.toExponential(2)} W` : "—"}
              </td>
              <td>{c.qor?.congestion != null ? c.qor.congestion.toFixed(3) : "—"}</td>
              <td>{c.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PdnTable({ rows }: { rows: Cand[] }) {
  if (!rows.length) return null;
  return (
    <div className="fl-dynir-group">
      <span>PDN · candidate extract / DirectLU / AMG (not gold)</span>
      <table className="fl-dynir-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Extract</th>
            <th>Droop</th>
            <th>EM J</th>
            <th>n_R</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id} data-status={c.status}>
              <td>
                {c.knobs?.source === "f4_iscale_champ" && c.knobs.host_source
                  ? `iscale-champ · ${c.knobs.host_source}`
                  : c.knobs?.source === "f4_iscale_win" && c.knobs.host_source
                    ? `iscale-win · ${c.knobs.host_source}`
                    : c.knobs?.source === "f4_iscale" && c.knobs.host_source
                      ? `iscale · ${c.knobs.host_source}`
                      : (c.knobs?.name ?? c.knobs?.source ?? c.id)}
              </td>
              <td>{c.knobs?.extract_id ?? c.artifacts?.extract ?? "finish"}</td>
              <td>
                {c.qor?.dynamic_ir_mv != null ? `${c.qor.dynamic_ir_mv.toFixed(3)} mV` : "—"}
              </td>
              <td>
                {c.qor?.em_j_a_m2 != null ? `${(c.qor.em_j_a_m2 / 1e9).toFixed(2)} GA/m²` : "—"}
              </td>
              <td>{c.artifacts?.n_r != null ? String(c.artifacts.n_r) : "—"}</td>
              <td>{c.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
    <section className="fl-dynir" aria-label="Physically-aware DSE">
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
          {report.n_ir_cell || report.n_ir_cell_champ || report.n_ir_cell_champ_cone || report.n_f4_ir_cell_champ_extract || report.n_f4_ir_cell_champ_cone_extract || report.n_ir_cell_champ_pdn || report.n_ir_cell_champ_cone_pdn || report.n_f4_ir_cell_champ_cone_region_extract || report.n_ir_cell_champ_cone_region_pdn || report.n_f4_amg_champ || report.n_f4_ras_champ || report.n_f4_krylov_champ || report.n_static_ir_steer || report.n_static_mesh || report.n_static_straps || report.n_em_straps || report.n_winning_ir_pdn || report.winning_static_mv != null || report.n_f4_ir_cell_extract || report.n_ir_cell_pdn || report.n_f4_ir_cell_region_extract || report.n_ir_cell_region_pdn || report.n_f4_iscale_champ ? (
            <details className="lb-raw">
            <summary>Raw IR-loop tape</summary>
            <p className="fl-dynir-irloop" aria-label="IR-cell closed loop">
              IR loop
              {report.n_ir_cell != null ? ` · IR-c ${report.n_ir_cell}` : ""}
              {report.ir_cell_champ_wns_ns != null
                ? ` · IR-cc ${report.ir_cell_champ_modules ?? "dpath"} WNS ${report.ir_cell_champ_wns_ns >= 0 ? "+" : ""}${report.ir_cell_champ_wns_ns.toFixed(3)}`
                : report.n_ir_cell_champ != null
                  ? ` · IR-cc ${report.n_ir_cell_champ}`
                  : ""}
              {report.ir_cell_champ_extract_mv != null
                ? ` · IR-cx ${report.ir_cell_champ_extract_mv.toFixed(3)} mV${
                    report.ir_cell_champ_extract_residual_mv != null
                      ? ` Δ=${report.ir_cell_champ_extract_residual_mv >= 0 ? "+" : ""}${report.ir_cell_champ_extract_residual_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_ir_cell_champ_extract != null
                  ? ` · IR-cx ${report.n_f4_ir_cell_champ_extract}`
                  : ""}
              {report.ir_cell_champ_pdn_mv != null
                ? ` · IR-cp ${report.ir_cell_champ_pdn_name ?? "PDN"} ${report.ir_cell_champ_pdn_mv.toFixed(3)} mV${
                    report.ir_cell_champ_pdn_vs_host_win_mv != null
                      ? ` vs host-win ${report.ir_cell_champ_pdn_vs_host_win_mv >= 0 ? "+" : ""}${report.ir_cell_champ_pdn_vs_host_win_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_ir_cell_champ_pdn != null
                  ? ` · IR-cp ${report.n_ir_cell_champ_pdn}`
                  : ""}
              {report.ir_cell_champ_cone_wns_ns != null
                ? ` · IR-cn ${report.ir_cell_champ_cone_modules ?? "dpath"} WNS ${report.ir_cell_champ_cone_wns_ns >= 0 ? "+" : ""}${report.ir_cell_champ_cone_wns_ns.toFixed(3)}`
                : report.n_ir_cell_champ_cone != null
                  ? ` · IR-cn ${report.n_ir_cell_champ_cone}`
                  : ""}
              {report.ir_cell_champ_cone_extract_mv != null
                ? ` · IR-cne ${report.ir_cell_champ_cone_extract_mv.toFixed(3)} mV${
                    report.ir_cell_champ_cone_extract_residual_mv != null
                      ? ` Δ=${report.ir_cell_champ_cone_extract_residual_mv >= 0 ? "+" : ""}${report.ir_cell_champ_cone_extract_residual_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_ir_cell_champ_cone_extract != null
                  ? ` · IR-cne ${report.n_f4_ir_cell_champ_cone_extract}`
                  : ""}
              {report.ir_cell_champ_cone_pdn_mv != null
                ? ` · IR-cnp ${report.ir_cell_champ_cone_pdn_name ?? "PDN"} ${report.ir_cell_champ_cone_pdn_mv.toFixed(3)} mV${
                    report.ir_cell_champ_cone_pdn_vs_host_win_mv != null
                      ? ` vs host-win ${report.ir_cell_champ_cone_pdn_vs_host_win_mv >= 0 ? "+" : ""}${report.ir_cell_champ_cone_pdn_vs_host_win_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_ir_cell_champ_cone_pdn != null
                  ? ` · IR-cnp ${report.n_ir_cell_champ_cone_pdn}`
                  : ""}
              {report.ir_cell_champ_cone_region_mv != null
                ? ` · IR-cnr ${report.ir_cell_champ_cone_region_mv.toFixed(3)} mV${
                    report.ir_cell_champ_cone_region_bin ? ` ${report.ir_cell_champ_cone_region_bin}` : ""
                  }${
                    report.ir_cell_champ_cone_region_residual_mv != null
                      ? ` Δ=${report.ir_cell_champ_cone_region_residual_mv >= 0 ? "+" : ""}${report.ir_cell_champ_cone_region_residual_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_ir_cell_champ_cone_region_extract != null
                  ? ` · IR-cnr ${report.n_f4_ir_cell_champ_cone_region_extract}`
                  : ""}
              {report.ir_cell_champ_cone_region_pdn_mv != null
                ? ` · IR-cnrp ${report.ir_cell_champ_cone_region_pdn_name ?? "PDN"} ${report.ir_cell_champ_cone_region_pdn_mv.toFixed(3)} mV${
                    report.ir_cell_champ_cone_region_pdn_vs_host_win_mv != null
                      ? ` vs host-win ${report.ir_cell_champ_cone_region_pdn_vs_host_win_mv >= 0 ? "+" : ""}${report.ir_cell_champ_cone_region_pdn_vs_host_win_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_ir_cell_champ_cone_region_pdn != null
                  ? ` · IR-cnrp ${report.n_ir_cell_champ_cone_region_pdn}`
                  : ""}
              {report.winning_ir_region_mv != null
                ? ` · IR-wr ${report.winning_ir_region_mv.toFixed(3)} mV${
                    report.winning_ir_region_bin ? ` ${report.winning_ir_region_bin}` : ""
                  }${
                    report.winning_ir_region_residual_mv != null
                      ? ` Δ=${report.winning_ir_region_residual_mv >= 0 ? "+" : ""}${report.winning_ir_region_residual_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_winning_ir_region_extract != null
                  ? ` · IR-wr ${report.n_f4_winning_ir_region_extract}`
                  : ""}
              {report.winning_ir_region_pdn_mv != null
                ? ` · IR-wrp ${report.winning_ir_region_pdn_name ?? "PDN"} ${report.winning_ir_region_pdn_mv.toFixed(3)} mV${
                    report.winning_ir_region_pdn_vs_host_win_mv != null
                      ? ` vs host-win ${report.winning_ir_region_pdn_vs_host_win_mv >= 0 ? "+" : ""}${report.winning_ir_region_pdn_vs_host_win_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_winning_ir_region_pdn != null
                  ? ` · IR-wrp ${report.n_winning_ir_region_pdn}`
                  : ""}
              {report.winning_ir_region_cell_wns_ns != null
                ? ` · IR-wrc ${report.winning_ir_region_cell_modules ?? "dpath"} WNS ${report.winning_ir_region_cell_wns_ns >= 0 ? "+" : ""}${report.winning_ir_region_cell_wns_ns.toFixed(3)}`
                : report.n_winning_ir_region_cell != null
                  ? ` · IR-wrc ${report.n_winning_ir_region_cell}`
                  : ""}
              {report.winning_ir_region_cell_extract_mv != null
                ? ` · IR-wrce ${report.winning_ir_region_cell_extract_mv.toFixed(3)} mV${
                    report.winning_ir_region_cell_extract_residual_mv != null
                      ? ` Δ=${report.winning_ir_region_cell_extract_residual_mv >= 0 ? "+" : ""}${report.winning_ir_region_cell_extract_residual_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_winning_ir_region_cell_extract != null
                  ? ` · IR-wrce ${report.n_f4_winning_ir_region_cell_extract}`
                  : ""}
              {report.winning_ir_region_cell_pdn_mv != null
                ? ` · IR-wrcp ${report.winning_ir_region_cell_pdn_name ?? "PDN"} ${report.winning_ir_region_cell_pdn_mv.toFixed(3)} mV${
                    report.winning_ir_region_cell_pdn_vs_host_win_mv != null
                      ? ` vs host-win ${report.winning_ir_region_cell_pdn_vs_host_win_mv >= 0 ? "+" : ""}${report.winning_ir_region_cell_pdn_vs_host_win_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_winning_ir_region_cell_pdn != null
                  ? ` · IR-wrcp ${report.n_winning_ir_region_cell_pdn}`
                  : ""}
              {report.winning_ir_region_cell_leftover_wns_ns != null
                ? ` · IR-wrl ${report.winning_ir_region_cell_leftover_modules ?? "dpath"} WNS ${report.winning_ir_region_cell_leftover_wns_ns >= 0 ? "+" : ""}${report.winning_ir_region_cell_leftover_wns_ns.toFixed(3)}`
                : report.n_winning_ir_region_cell_leftover != null
                  ? ` · IR-wrl ${report.n_winning_ir_region_cell_leftover}`
                  : ""}
              {report.winning_ir_region_cell_leftover_extract_mv != null
                ? ` · IR-wrle ${report.winning_ir_region_cell_leftover_extract_mv.toFixed(3)} mV${
                    report.winning_ir_region_cell_leftover_extract_residual_mv != null
                      ? ` Δ=${report.winning_ir_region_cell_leftover_extract_residual_mv >= 0 ? "+" : ""}${report.winning_ir_region_cell_leftover_extract_residual_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_winning_ir_region_cell_leftover_extract != null
                  ? ` · IR-wrle ${report.n_f4_winning_ir_region_cell_leftover_extract}`
                  : ""}
              {report.winning_ir_region_cell_leftover_pdn_mv != null
                ? ` · IR-wrlp ${report.winning_ir_region_cell_leftover_pdn_name ?? "PDN"} ${report.winning_ir_region_cell_leftover_pdn_mv.toFixed(3)} mV${
                    report.winning_ir_region_cell_leftover_pdn_vs_host_win_mv != null
                      ? ` vs host-win ${report.winning_ir_region_cell_leftover_pdn_vs_host_win_mv >= 0 ? "+" : ""}${report.winning_ir_region_cell_leftover_pdn_vs_host_win_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_winning_ir_region_cell_leftover_pdn != null
                  ? ` · IR-wrlp ${report.n_winning_ir_region_cell_leftover_pdn}`
                  : ""}
              {report.refine && report.refine.length
                ? report.refine.map((fr) => {
                    const mv = fr.catalog_mv ?? fr.pdn_mv ?? fr.extract_mv;
                    const extra = mv != null ? ` ${mv.toFixed(3)} mV` : fr.n_cells != null ? ` n=${fr.n_cells}` : "";
                    return ` · ${fr.label ?? `refine[${fr.depth}]`}${extra}`;
                  }).join("")
                : report.winning_ir_region_cell_leftover2_wns_ns != null
                ? ` · IR-wrl2 ${report.winning_ir_region_cell_leftover2_modules ?? "dpath"} WNS ${report.winning_ir_region_cell_leftover2_wns_ns >= 0 ? "+" : ""}${report.winning_ir_region_cell_leftover2_wns_ns.toFixed(3)}`
                : report.n_winning_ir_region_cell_leftover2 != null
                  ? ` · IR-wrl2 ${report.n_winning_ir_region_cell_leftover2}`
                  : ""}
              {report.refine && report.refine.length
                ? ""
                : report.winning_ir_region_cell_leftover2_extract_mv != null
                ? ` · IR-wrl2e ${report.winning_ir_region_cell_leftover2_extract_mv.toFixed(3)} mV${
                    report.winning_ir_region_cell_leftover2_extract_residual_mv != null
                      ? ` Δ=${report.winning_ir_region_cell_leftover2_extract_residual_mv >= 0 ? "+" : ""}${report.winning_ir_region_cell_leftover2_extract_residual_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_winning_ir_region_cell_leftover2_extract != null
                  ? ` · IR-wrl2e ${report.n_f4_winning_ir_region_cell_leftover2_extract}`
                  : ""}
              {report.refine && report.refine.length
                ? ""
                : report.winning_ir_region_cell_leftover2_pdn_mv != null
                ? ` · IR-wrl2p ${report.winning_ir_region_cell_leftover2_pdn_name ?? "PDN"} ${report.winning_ir_region_cell_leftover2_pdn_mv.toFixed(3)} mV${
                    report.winning_ir_region_cell_leftover2_pdn_vs_host_win_mv != null
                      ? ` vs host-win ${report.winning_ir_region_cell_leftover2_pdn_vs_host_win_mv >= 0 ? "+" : ""}${report.winning_ir_region_cell_leftover2_pdn_vs_host_win_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_winning_ir_region_cell_leftover2_pdn != null
                  ? ` · IR-wrl2p ${report.n_winning_ir_region_cell_leftover2_pdn}`
                  : ""}
              {report.ir_champ_amg_mv != null
                ? ` · AMG-c ${report.ir_champ_amg_mv.toFixed(3)} mV${
                    report.ir_champ_amg_vs_direct_mv != null
                      ? ` Δ=${report.ir_champ_amg_vs_direct_mv >= 0 ? "+" : ""}${report.ir_champ_amg_vs_direct_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_amg_champ != null
                  ? ` · AMG-c ${report.n_f4_amg_champ}`
                  : ""}
              {report.ir_champ_ras_mv != null
                ? ` · RAS-c ${report.ir_champ_ras_mv.toFixed(3)} mV${
                    report.ir_champ_ras_vs_direct_mv != null
                      ? ` Δ=${report.ir_champ_ras_vs_direct_mv >= 0 ? "+" : ""}${report.ir_champ_ras_vs_direct_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_ras_champ != null
                  ? ` · RAS-c ${report.n_f4_ras_champ}`
                  : ""}
              {report.ir_champ_krylov_mv != null
                ? ` · Kry-c ${report.ir_champ_krylov_mv.toFixed(3)} mV${
                    report.ir_champ_krylov_vs_direct_mv != null
                      ? ` Δ=${report.ir_champ_krylov_vs_direct_mv >= 0 ? "+" : ""}${report.ir_champ_krylov_vs_direct_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_krylov_champ != null
                  ? ` · Kry-c ${report.n_f4_krylov_champ}`
                  : ""}
              {report.static_ir_steer_mv != null
                ? ` · SI ${report.static_ir_steer_name ?? "pkg_r"} ${report.static_ir_steer_mv.toFixed(3)} mV${
                    report.static_ir_steer_vs_champ_mv != null
                      ? ` Δ=${report.static_ir_steer_vs_champ_mv >= 0 ? "+" : ""}${report.static_ir_steer_vs_champ_mv.toFixed(3)}`
                      : ""
                  }`
                : report.winning_static_mv != null
                  ? ` · SI-champ ${report.winning_static_mv.toFixed(3)} mV`
                  : report.n_static_ir_steer != null
                    ? ` · SI ${report.n_static_ir_steer}`
                    : ""}
              {report.static_mesh_mv != null
                ? ` · SM ${report.static_mesh_name ?? "bumps"} ${report.static_mesh_mv.toFixed(3)} mV${
                    report.static_mesh_vs_champ_mv != null
                      ? ` Δ=${report.static_mesh_vs_champ_mv >= 0 ? "+" : ""}${report.static_mesh_vs_champ_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_static_mesh != null
                  ? ` · SM ${report.n_static_mesh}`
                  : ""}
              {report.static_straps_mv != null
                ? ` · ST ${report.static_straps_name ?? "straps"} ${report.static_straps_mv.toFixed(3)} mV${
                    report.static_straps_vs_champ_mv != null
                      ? ` Δ=${report.static_straps_vs_champ_mv >= 0 ? "+" : ""}${report.static_straps_vs_champ_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_static_straps != null
                  ? ` · ST ${report.n_static_straps}`
                  : ""}
              {report.em_straps_j != null
                ? ` · EM ${report.em_straps_name ?? "width"} ${(report.em_straps_j / 1e9).toFixed(2)}e9${
                    report.em_straps_vs_strap_j != null
                      ? ` Δstrap=${report.em_straps_vs_strap_j >= 0 ? "+" : ""}${(report.em_straps_vs_strap_j / 1e9).toFixed(2)}e9`
                      : ""
                  }${
                    report.em_straps_vs_champ_j != null
                      ? ` Δchamp=${report.em_straps_vs_champ_j >= 0 ? "+" : ""}${(report.em_straps_vs_champ_j / 1e9).toFixed(2)}e9`
                      : ""
                  }`
                : report.n_em_straps != null
                  ? ` · EM ${report.n_em_straps}`
                  : ""}
              {report.winning_ir_pdn_mv != null
                ? ` · IR-w ${report.winning_ir_pdn_name ?? "catalog"} ${report.winning_ir_pdn_mv.toFixed(3)} mV${
                    report.winning_ir_pdn_vs_champ_mv != null
                      ? ` Δ=${report.winning_ir_pdn_vs_champ_mv >= 0 ? "+" : ""}${report.winning_ir_pdn_vs_champ_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_winning_ir_pdn != null
                  ? ` · IR-w ${report.n_winning_ir_pdn}`
                  : ""}
              {report.ir_cell_extract_mv != null
                ? ` · IR-x ${report.ir_cell_extract_mv.toFixed(3)} mV${
                    report.ir_cell_extract_residual_mv != null
                      ? ` Δ=${report.ir_cell_extract_residual_mv >= 0 ? "+" : ""}${report.ir_cell_extract_residual_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_ir_cell_extract != null
                  ? ` · IR-x ${report.n_f4_ir_cell_extract}`
                  : ""}
              {report.ir_cell_pdn_mv != null
                ? ` · IR-p ${report.ir_cell_pdn_name ?? "PDN"} ${report.ir_cell_pdn_mv.toFixed(3)} mV`
                : report.n_ir_cell_pdn != null
                  ? ` · IR-p ${report.n_ir_cell_pdn}`
                  : ""}
              {report.ir_cell_region_mv != null
                ? ` · IR-r ${report.ir_cell_region_mv.toFixed(3)} mV${
                    report.ir_cell_region_bin ? ` ${report.ir_cell_region_bin}` : ""
                  }${
                    report.ir_cell_region_residual_mv != null
                      ? ` Δ=${report.ir_cell_region_residual_mv >= 0 ? "+" : ""}${report.ir_cell_region_residual_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_ir_cell_region_extract != null
                  ? ` · IR-r ${report.n_f4_ir_cell_region_extract}`
                  : ""}
              {report.ir_cell_region_pdn_mv != null
                ? ` · IR-rp ${report.ir_cell_region_pdn_name ?? "PDN"} ${report.ir_cell_region_pdn_mv.toFixed(3)} mV${
                    report.ir_cell_region_pdn_vs_host_win_mv != null
                      ? ` vs host-win ${report.ir_cell_region_pdn_vs_host_win_mv >= 0 ? "+" : ""}${report.ir_cell_region_pdn_vs_host_win_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_ir_cell_region_pdn != null
                  ? ` · IR-rp ${report.n_ir_cell_region_pdn}`
                  : ""}
              {report.ir_cell_iscale_champ_mv != null
                ? ` · I×c ×${(report.ir_cell_iscale_champ_scale ?? 0).toFixed(2)} ${report.ir_cell_iscale_champ_mv.toFixed(3)} mV${
                    report.ir_cell_iscale_champ_vs_win_mv != null
                      ? ` vs I×w ${report.ir_cell_iscale_champ_vs_win_mv >= 0 ? "+" : ""}${report.ir_cell_iscale_champ_vs_win_mv.toFixed(3)}`
                      : ""
                  }`
                : report.n_f4_iscale_champ != null
                  ? ` · I×c ${report.n_f4_iscale_champ}`
                  : ""}
            </p>
            </details>
          ) : null}
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
                {report.n_f4_host_region_extract != null
                  ? ` · host-r ${report.n_f4_host_region_extract}`
                  : ""}
                {report.n_f4_region_extract != null ? ` · r-ext ${report.n_f4_region_extract}` : ""}
                {report.n_f4_amg != null ? ` · AMG ${report.n_f4_amg}` : ""}
                {report.n_f4_iscale != null ? ` · I× ${report.n_f4_iscale}` : ""}
                {report.n_f4_iscale_win != null ? ` · I×w ${report.n_f4_iscale_win}` : ""}
                {report.n_f4_iscale_champ != null ? ` · I×c ${report.n_f4_iscale_champ}` : ""}
                {report.n_f4_ir_cell_champ_extract != null ? ` · IR-cx ${report.n_f4_ir_cell_champ_extract}` : ""}
                {report.n_ir_cell_champ_pdn != null ? ` · IR-cp ${report.n_ir_cell_champ_pdn}` : ""}
                {report.n_f4_ir_cell_champ_cone_extract != null ? ` · IR-cne ${report.n_f4_ir_cell_champ_cone_extract}` : ""}
                {report.n_ir_cell_champ_cone_pdn != null ? ` · IR-cnp ${report.n_ir_cell_champ_cone_pdn}` : ""}
                {report.n_f4_ir_cell_champ_cone_region_extract != null
                  ? ` · IR-cnr ${report.n_f4_ir_cell_champ_cone_region_extract}`
                  : ""}
                {report.n_ir_cell_champ_cone_region_pdn != null
                  ? ` · IR-cnrp ${report.n_ir_cell_champ_cone_region_pdn}`
                  : ""}
                {report.n_f4_winning_ir_region_extract != null
                  ? ` · IR-wr ${report.n_f4_winning_ir_region_extract}`
                  : ""}
                {report.n_winning_ir_region_pdn != null
                  ? ` · IR-wrp ${report.n_winning_ir_region_pdn}`
                  : ""}
                {report.n_winning_ir_region_cell != null
                  ? ` · IR-wrc ${report.n_winning_ir_region_cell}`
                  : ""}
                {report.n_f4_winning_ir_region_cell_extract != null
                  ? ` · IR-wrce ${report.n_f4_winning_ir_region_cell_extract}`
                  : ""}
                {report.n_winning_ir_region_cell_pdn != null
                  ? ` · IR-wrcp ${report.n_winning_ir_region_cell_pdn}`
                  : ""}
                {report.n_winning_ir_region_cell_leftover != null
                  ? ` · IR-wrl ${report.n_winning_ir_region_cell_leftover}`
                  : ""}
                {report.n_f4_winning_ir_region_cell_leftover_extract != null
                  ? ` · IR-wrle ${report.n_f4_winning_ir_region_cell_leftover_extract}`
                  : ""}
                {report.n_winning_ir_region_cell_leftover_pdn != null
                  ? ` · IR-wrlp ${report.n_winning_ir_region_cell_leftover_pdn}`
                  : ""}
                {report.refine && report.refine.length
                  ? report.refine.map((fr) => ` · ${fr.label ?? `refine[${fr.depth}]`}`).join("")
                  : report.n_winning_ir_region_cell_leftover2 != null
                    ? ` · IR-wrl2 ${report.n_winning_ir_region_cell_leftover2}`
                    : ""}
                {report.refine && report.refine.length
                  ? ""
                  : report.n_f4_winning_ir_region_cell_leftover2_extract != null
                    ? ` · IR-wrl2e ${report.n_f4_winning_ir_region_cell_leftover2_extract}`
                    : ""}
                {report.refine && report.refine.length
                  ? ""
                  : report.n_winning_ir_region_cell_leftover2_pdn != null
                    ? ` · IR-wrl2p ${report.n_winning_ir_region_cell_leftover2_pdn}`
                    : ""}
                {report.n_f4_amg_champ != null ? ` · AMG-c ${report.n_f4_amg_champ}` : ""}
                {report.n_f4_ras_champ != null ? ` · RAS-c ${report.n_f4_ras_champ}` : ""}
                {report.n_f4_krylov_champ != null ? ` · Kry-c ${report.n_f4_krylov_champ}` : ""}
                {report.n_static_ir_steer != null ? ` · SI ${report.n_static_ir_steer}` : ""}
                {report.n_static_mesh != null ? ` · SM ${report.n_static_mesh}` : ""}
                {report.n_static_straps != null ? ` · ST ${report.n_static_straps}` : ""}
                {report.n_em_straps != null ? ` · EM ${report.n_em_straps}` : ""}
                {report.n_winning_ir_pdn != null ? ` · IR-w ${report.n_winning_ir_pdn}` : ""}
                {report.n_f4_ir_cell_extract != null ? ` · IR-x ${report.n_f4_ir_cell_extract}` : ""}
                {report.n_ir_cell_pdn != null ? ` · IR-p ${report.n_ir_cell_pdn}` : ""}
                {report.n_f4_ir_cell_region_extract != null
                  ? ` · IR-r ${report.n_f4_ir_cell_region_extract}`
                  : ""}
                {report.n_ir_cell_region_pdn != null ? ` · IR-rp ${report.n_ir_cell_region_pdn}` : ""}
                {report.n_host_ir_steer != null ? ` · h-IR ${report.n_host_ir_steer}` : ""}
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

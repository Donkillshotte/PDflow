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
    dynamic_ir_mv?: number | null;
    congestion?: number | null;
    wns_cost?: number | null;
    power_w?: number | null;
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
  n_host_ir_steer?: number;
  n_port_steer?: number;
  n_f4_solve?: number;
  surrogate_f1_to_f2_gnn?: { n?: number; uncertainty?: string; via?: string };
  pareto?: { logic?: string[]; architecture?: string[]; physical?: string[]; note?: string };
  attribution?: Attr;
  focus?: { focus?: string; scope?: string };
  plan?: { steps?: { level?: string; reason?: string }[] };
  candidates?: Cand[];
};

const LEVELS = ["architecture", "logic", "synthesis", "cell", "net", "physical", "routing", "pdn"] as const;

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
  const frontLogic = new Set(report?.pareto?.logic ?? []);
  const frontArch = new Set(report?.pareto?.architecture ?? []);

  return (
    <section className="fl-dynir" aria-label="DSE fisico-aware">
      <header className="fl-dynir-head">
        <strong>DSE · ricerca a livelli</strong>
        <p>
          Planner IR+WNS · EHVI · F2/F5-lite SPEF · extract PDN · STA F3 · IR/EM F4 ·{" "}
          <Link href="/materiali/reference/dse.md">dse.md</Link>
        </p>
      </header>
      {!report?.ok ? (
        <p className="fl-dynir-empty">
          Report assente — esegui l’azione <code>dse</code> (F5-lite, non <code>make finish</code>).
        </p>
      ) : (
        <>
          <p className="fl-dynir-summary">{report.summary}</p>
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
              <dt>Candidati</dt>
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
                {report.n_host_ir_steer != null ? ` · h-IR ${report.n_host_ir_steer}` : ""}
                {report.n_f4_solve != null ? ` · solve ${report.n_f4_solve}` : ""}
              </dd>
            </div>
            <div>
              <dt>Pareto logic</dt>
              <dd>{report.pareto?.logic?.length ?? 0}</dd>
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
              <dt>Cono IR</dt>
              <dd>
                {(report.attribution?.modules ?? []).join(", ") || "—"}
                {report.focus?.scope ? ` · ${report.focus.scope}` : ""}
              </dd>
            </div>
          </dl>
          {report.plan?.steps?.length ? (
            <details className="fl-dynir-plan">
              <summary>Piano · {report.plan.steps.length} passi</summary>
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
            title="Logic · sequenze ABC"
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
            <th>Nome</th>
            <th>F</th>
            <th>Area µm²</th>
            <th>WNS</th>
            <th>Stato</th>
            <th>Pareto</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id} data-status={c.status}>
              <td>{c.knobs?.name ?? c.knobs?.extract ?? c.id}</td>
              <td>{c.fidelity}</td>
              <td>{c.qor?.area_um2 != null ? c.qor.area_um2.toFixed(3) : "—"}</td>
              <td>
                {c.qor?.wns_cost != null ? `${(-c.qor.wns_cost).toFixed(3)} ns` : "—"}
              </td>
              <td>{c.status}</td>
              <td>{front.has(c.id) ? "sì" : ""}</td>
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
      <span>Physical / routing · F2-fast / GPL / GRT / F5-lite SPEF (non IR)</span>
      <table className="fl-dynir-table">
        <thead>
          <tr>
            <th>Fonte</th>
            <th>F</th>
            <th>HPWL</th>
            <th>WNS</th>
            <th>Cong</th>
            <th>Stato</th>
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
                {c.artifacts?.hpwl_um != null
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
      <span>PDN · extract candidato / DirectLU / AMG (non gold)</span>
      <table className="fl-dynir-table">
        <thead>
          <tr>
            <th>Fonte</th>
            <th>Extract</th>
            <th>Droop</th>
            <th>EM J</th>
            <th>n_R</th>
            <th>Stato</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id} data-status={c.status}>
              <td>
                {c.knobs?.source === "f4_iscale" && c.knobs.host_source
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

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Cand = {
  id: string;
  level: string;
  fidelity: string;
  status: string;
  knobs?: { name?: string; extract?: string };
  qor?: {
    area_um2?: number | null;
    dynamic_ir_mv?: number | null;
    congestion?: number | null;
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
  pareto?: { logic?: string[]; architecture?: string[]; physical?: string[]; note?: string };
  attribution?: Attr;
  focus?: { focus?: string; scope?: string };
  plan?: { steps?: { level?: string; reason?: string }[] };
  candidates?: Cand[];
};

const LEVELS = ["architecture", "logic", "synthesis", "physical", "pdn"] as const;

export function DsePanel() {
  const [report, setReport] = useState<DseReport | null>(null);

  const load = useCallback(async () => {
    const r = await fetch("/api/content?path=sim/reports/dse_flowlab.json");
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
          Planner dal cono IR · ABC BOiLS/DRiLLS · F2-fast sul netlist · IR F4 ·{" "}
          <Link href="/materiali/reference/dse.md">dse.md</Link>
        </p>
      </header>
      {!report?.ok ? (
        <p className="fl-dynir-empty">
          Report assente — esegui l’azione <code>dse</code> (non lancia P&amp;R).
        </p>
      ) : (
        <>
          <p className="fl-dynir-summary">{report.summary}</p>
          {report.plan?.steps?.[0]?.reason ? (
            <p className="fl-dynir-summary">Piano: {report.plan.steps[0].reason}</p>
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
              <dt>Pareto logic</dt>
              <dd>{report.pareto?.logic?.length ?? 0}</dd>
            </div>
            <div>
              <dt>Cono IR</dt>
              <dd>
                {(report.attribution?.modules ?? []).join(", ") || "—"}
                {report.focus?.scope ? ` · ${report.focus.scope}` : ""}
              </dd>
            </div>
          </dl>
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
              <td>{c.status}</td>
              <td>{front.has(c.id) ? "sì" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

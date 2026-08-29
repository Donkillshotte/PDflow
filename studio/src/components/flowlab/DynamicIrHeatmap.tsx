"use client";

import { useCallback, useEffect, useState } from "react";

type Hottest = { node?: string; ir_mv?: number; x?: number; y?: number };
type DynReport = {
  ok?: boolean;
  summary?: string;
  mode?: string;
  vdd?: number;
  dynamic?: { worst_droop?: number; worst_droop_pct?: number; worst_time_s?: number };
  static?: { worst_ir?: number };
  heatmap?: { taps?: number; ir_max_mv?: number; hottest?: Hottest[] };
  ngspice_gold?: { ok?: boolean; abs_err_mv?: number } | null;
};

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

  return (
    <section className="fl-dynir" aria-label="Dynamic IR heatmap">
      <header className="fl-dynir-head">
        <strong>Dynamic IR · I(t) per pin</strong>
        <p>
          OpenROAD mesh + PWL + backward Euler · non è RedHawk ·{" "}
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
          </dl>
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

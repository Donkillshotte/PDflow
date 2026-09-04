"use client";

import { useCallback, useEffect, useState } from "react";

type GateRow = {
  inst?: string;
  cell?: string;
  pin?: string;
  delay_ns?: number;
  delay_ir_ns?: number;
  v_inst?: number;
  ir_mv?: number | null;
  joined?: boolean;
  scale?: number;
};

type CellRow = {
  inst?: string;
  cell?: string;
  ir_mv?: number | null;
  v_inst?: number;
  on_worst_path?: boolean;
};

type StaIr = {
  ok?: boolean;
  slack_ns?: number | null;
  slack_ir_ns?: number | null;
  n_joined?: number | null;
  n_gates?: number | null;
  degradation_ps?: number | null;
  worst_cell_ir_mv?: number | null;
  map?: string | null;
  path_gates?: GateRow[];
  hottest_cells?: CellRow[];
  note?: string;
  report?: string;
};

function fmtNs(v: number | null | undefined): string {
  return v == null || Number.isNaN(v) ? "—" : `${v.toFixed(4)} ns`;
}

function fmtMv(v: number | null | undefined): string {
  return v == null || Number.isNaN(v) ? "—" : `${v.toFixed(3)} mV`;
}

export function StaIrAwarePanel({
  variant = "flowlab",
  busy,
  onRun,
}: {
  variant?: string;
  busy?: string | null;
  onRun?: (action: string, long: boolean) => void;
}) {
  const [data, setData] = useState<StaIr | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`/api/signoff?variant=${encodeURIComponent(variant)}`);
      if (!res.ok) throw new Error(`signoff ${res.status}`);
      const json = (await res.json()) as { staIr?: StaIr | null };
      setData(json.staIr ?? null);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "STA IR error");
    }
  }, [variant]);

  useEffect(() => {
    void refresh();
  }, [refresh, busy]);

  const slack = data?.slack_ns ?? null;
  const slackIr = data?.slack_ir_ns ?? null;
  const extraPs =
    slack != null && slackIr != null ? (slack - slackIr) * 1e3 : data?.degradation_ps ?? null;

  return (
    <div className="sta-ir-panel" id="sta-ir">
      <div className="sta-ir-head">
        <strong>STA IR-aware</strong>
        <p>
          OpenSTA worst max path with the finish SPEF (same parasitics as
          sta_signoff), then NLDM typical-V × (Vdd/V<sub>inst</sub>)<sup>α</sup> on
          ITerm-joined cells from the current_run map. Nets stay nominal. Not
          PrimeTime / Tempus. A MET overlay on ideal RC is not a WNS close.
          Gold Dynamic IR 45.298 mV is another extract.
        </p>
      </div>
      {err && <p className="sig-err">{err}</p>}
      {data ? (
        <>
          <dl className="sta-ir-metrics">
            <div>
              <dt>STA slack</dt>
              <dd>{fmtNs(slack)}</dd>
            </div>
            <div>
              <dt>IR slack</dt>
              <dd>{fmtNs(slackIr)}</dd>
            </div>
            <div>
              <dt>Extra delay</dt>
              <dd>{extraPs == null ? "—" : `${extraPs.toFixed(2)} ps`}</dd>
            </div>
            <div>
              <dt>Gates joined</dt>
              <dd>
                {data.n_joined ?? "—"}/{data.n_gates ?? "—"}
              </dd>
            </div>
            <div>
              <dt>Worst cell IR</dt>
              <dd>{fmtMv(data.worst_cell_ir_mv)}</dd>
            </div>
          </dl>
          {data.map ? (
            <p className="sta-ir-map">
              current_run map <code>{data.map}</code>
            </p>
          ) : null}
          {data.path_gates && data.path_gates.length > 0 && (
            <details className="sta-ir-gates">
              <summary>Per-gate IR overlay ({data.path_gates.length})</summary>
              <table className="sta-ir-table">
                <thead>
                  <tr>
                    <th>Gate</th>
                    <th>V</th>
                    <th>IR</th>
                    <th>Delay</th>
                    <th>Delay IR</th>
                  </tr>
                </thead>
                <tbody>
                  {data.path_gates.map((g, i) => (
                    <tr key={`${g.inst ?? "g"}-${i}`} className={g.joined ? undefined : "is-gap"}>
                      <td>
                        <code>{g.inst}</code>
                        {g.cell ? <small> {g.cell}</small> : null}
                      </td>
                      <td>{g.v_inst != null ? `${g.v_inst.toFixed(4)} V` : "—"}</td>
                      <td>{fmtMv(g.ir_mv)}</td>
                      <td>{fmtNs(g.delay_ns)}</td>
                      <td>{fmtNs(g.delay_ir_ns)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
          {data.hottest_cells && data.hottest_cells.length > 0 && (
            <p className="sta-ir-hot">
              Hottest joined cells:{" "}
              {data.hottest_cells.slice(0, 4).map((c, i) => (
                <span key={`${c.inst}-${i}`}>
                  {i ? " · " : ""}
                  <code>{c.inst}</code> {fmtMv(c.ir_mv)}
                </span>
              ))}
            </p>
          )}
        </>
      ) : (
        <p className="sta-ir-empty">
          Report missing — run Dynamic IR (current_run map) then STA IR-aware.
        </p>
      )}
      {onRun && (
        <button
          type="button"
          className="sig-run-btn"
          disabled={Boolean(busy)}
          onClick={() => onRun("sta_ir_aware", false)}
        >
          {busy === "sta_ir_aware" ? "…" : "Run STA IR-aware"}
        </button>
      )}
    </div>
  );
}

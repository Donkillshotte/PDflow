"use client";

import { useEffect, useState } from "react";

type Mesh = {
  id: string;
  mesh?: string;
  static_mv?: number | null;
  dynamic_mv?: number | null;
  gold?: boolean;
  em_checked?: number | null;
  note?: string;
};

type Ledger = {
  comparable?: boolean;
  note?: string;
  meshes?: Mesh[];
};

function fmt(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return `${Number(v).toFixed(2)} mV`;
}

export function IrMeshLedger() {
  const [ledger, setLedger] = useState<Ledger | null>(null);

  useEffect(() => {
    void fetch("/api/report?name=power_signoff_flowlab.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (j?.ir_mesh_ledger) setLedger(j.ir_mesh_ledger as Ledger);
      })
      .catch(() => undefined);
  }, []);

  if (!ledger?.meshes?.length) return null;

  return (
    <section className="fl-ir-ledger" aria-label="IR mesh ledger">
      <header>
        <strong>IR meshes</strong>
        <p>
          {ledger.comparable
            ? "Meshes marked comparable."
            : "These droop numbers are not interchangeable. Gold stays 45.298 mV."}
        </p>
      </header>
      <table>
        <thead>
          <tr>
            <th>Mesh</th>
            <th>Static</th>
            <th>Dynamic</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {ledger.meshes.map((m) => (
            <tr key={m.id}>
              <td>
                <code>{m.id}</code>
                {m.gold ? " · LOCKED" : ""}
              </td>
              <td>{fmt(m.static_mv)}</td>
              <td>{fmt(m.dynamic_mv)}</td>
              <td>
                {m.em_checked === 0
                  ? "em_checked 0 · no emlimit"
                  : m.note ?? m.mesh ?? ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

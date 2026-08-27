"use client";

import { Activity, Grid3X3, ShieldCheck } from "lucide-react";

const SIGNOFF = [
  {
    id: "gridcheck",
    label: "Gridcheck PDN",
    hint: "check_power_grid su floorplan PDN",
    icon: Grid3X3,
    long: false,
  },
  {
    id: "system_pdn",
    label: "System PDN",
    hint: "Z(f) · die droop · ngspice",
    icon: Activity,
    long: false,
  },
  {
    id: "activity_power",
    label: "Activity → power",
    hint: "set_power_activity + report",
    icon: Activity,
    long: false,
  },
  {
    id: "klayout_drc",
    label: "KLayout DRC",
    hint: "DRC su GDS finale · può richiedere minuti",
    icon: ShieldCheck,
    long: true,
  },
] as const;

export function FlowLabSignoff({
  disabled,
  busy,
  onRun,
}: {
  disabled?: boolean;
  busy?: string | null;
  onRun: (action: string, long: boolean) => void;
}) {
  return (
    <div className="fl-signoff">
      <div className="fl-signoff-head">
        <strong>Signoff post-finish</strong>
        <p>Analisi estese collegate alla variante <code>flowlab</code>.</p>
      </div>
      <div className="fl-signoff-grid">
        {SIGNOFF.map((s) => {
          const Icon = s.icon;
          return (
            <button
              key={s.id}
              type="button"
              className="fl-signoff-card"
              disabled={disabled || busy === s.id}
              onClick={() => onRun(s.id, s.long)}
            >
              <Icon size={18} aria-hidden />
              <div>
                <strong>{busy === s.id ? "Eseguo…" : s.label}</strong>
                <span>{s.hint}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

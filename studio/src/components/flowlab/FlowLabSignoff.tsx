"use client";

import { Activity, Download, Grid3X3, Layers, ShieldCheck, Zap } from "lucide-react";

const SIGNOFF = [
  {
    id: "activity_power",
    label: "Activity → power",
    hint: "VCD o synthetic · I_avg",
    icon: Activity,
    long: false,
  },
  {
    id: "chip_pdn_ir",
    label: "Chip IR mesh",
    hint: "write_pg_spice · pdn_transient",
    icon: Zap,
    long: true,
  },
  {
    id: "system_pdn",
    label: "System PDN",
    hint: "Z(f) · die droop · ngspice",
    icon: Layers,
    long: false,
  },
  {
    id: "export_spice_lab",
    label: "Export SPICE lab",
    hint: "sim/spice/ netlist + stats",
    icon: Download,
    long: false,
  },
  {
    id: "power_chain",
    label: "Catena SPICE",
    hint: "activity → chip IR → system → lab",
    icon: Activity,
    long: true,
  },
  {
    id: "gridcheck",
    label: "Gridcheck PDN",
    hint: "check_power_grid su floorplan PDN",
    icon: Grid3X3,
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
        <strong>Signoff power &amp; SPICE</strong>
        <p>
          Catena: VCD/activity → chip mesh → System PDN → export lab. Docs{" "}
          <a href="/materiali/reference/spice-power-chain.md">spice-power-chain</a>.
        </p>
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

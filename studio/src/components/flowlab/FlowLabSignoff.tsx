"use client";

import {
  Activity,
  Clock,
  Download,
  Grid3X3,
  Layers,
  Package,
  ShieldCheck,
  Thermometer,
  Zap,
} from "lucide-react";
import { SignoffMatrixPanel } from "./SignoffMatrixPanel";
import { DynamicIrHeatmap } from "./DynamicIrHeatmap";

type SignoffAction = {
  id: string;
  label: string;
  hint: string;
  icon: typeof Activity;
  long: boolean;
};

const POWER_ACTIONS: SignoffAction[] = [
  {
    id: "activity_power",
    label: "Activity → power",
    hint: "VCD o synthetic · I_avg",
    icon: Activity,
    long: false,
  },
  {
    id: "vectorless",
    label: "Vectorless / dynamic",
    hint: "Najm P01 · IR senza vettori",
    icon: Zap,
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
    id: "vyges_em_ir",
    label: "vyges-em-ir",
    hint: "engine Apache-2.0 · CG + BE",
    icon: Zap,
    long: false,
  },
  {
    id: "dynamic_ir",
    label: "Dynamic IR I(t)",
    hint: "A gold · B SA-AMG · heatmap",
    icon: Zap,
    long: false,
  },
  {
    id: "dse",
    label: "DSE fisico-aware",
    hint: "e-graph dpath · BOiLS · oracolo IR",
    icon: Layers,
    long: false,
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
    id: "power_signoff",
    label: "Power signoff",
    hint: "4 step + gate golden",
    icon: Zap,
    long: true,
  },
  {
    id: "gridcheck",
    label: "Gridcheck PDN",
    hint: "check_power_grid su floorplan PDN",
    icon: Grid3X3,
    long: false,
  },
];

const FINISH_ACTIONS: SignoffAction[] = [
  {
    id: "sta_signoff",
    label: "STA signoff",
    hint: "WNS/TNS vs golden-metrics",
    icon: Clock,
    long: false,
  },
  {
    id: "yosys_equiv",
    label: "Yosys equiv",
    hint: "EQY-class RTL↔synth",
    icon: ShieldCheck,
    long: false,
  },
  {
    id: "formal_gcd",
    label: "Formal SAT",
    hint: "reset |-> !resp_val",
    icon: ShieldCheck,
    long: false,
  },
  {
    id: "openrcx_report",
    label: "OpenRCX SPEF",
    hint: "StarRC-class extract",
    icon: Layers,
    long: false,
  },
  {
    id: "drc_signoff",
    label: "DRC signoff",
    hint: "Route DRC + KLayout GDS",
    icon: ShieldCheck,
    long: true,
  },
  {
    id: "klayout_lvs",
    label: "LVS signoff",
    hint: "GDS vs CDL · ORFS make lvs",
    icon: ShieldCheck,
    long: true,
  },
  {
    id: "klayout_drc",
    label: "KLayout DRC (solo GDS)",
    hint: "Legacy · usa drc_signoff per unificato",
    icon: ShieldCheck,
    long: true,
  },
];

const PHASE2_ACTIONS: SignoffAction[] = [
  {
    id: "thermal_signoff",
    label: "Thermal proxy",
    hint: "IR + droop → hotspot estimate",
    icon: Thermometer,
    long: false,
  },
  {
    id: "pkg_signoff",
    label: "PKG signoff",
    hint: "Bump config + RDL edu + system PDN",
    icon: Package,
    long: false,
  },
  {
    id: "pkg_bump",
    label: "PKG bump",
    hint: "default.json + mesh SPICE sources",
    icon: Package,
    long: false,
  },
  {
    id: "pkg_rdl",
    label: "PKG RDL (edu)",
    hint: "rdl_route API map · no bump LEF on GCD",
    icon: Package,
    long: false,
  },
  {
    id: "signoff_phase2",
    label: "Signoff Fase 2",
    hint: "Thermal proxy + PKG bump/RDL",
    icon: Package,
    long: false,
  },
];

function ActionGrid({
  actions,
  disabled,
  busy,
  onRun,
}: {
  actions: SignoffAction[];
  disabled?: boolean;
  busy?: string | null;
  onRun: (action: string, long: boolean) => void;
}) {
  return (
    <div className="fl-signoff-grid">
      {actions.map((s) => {
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
  );
}

export function FlowLabSignoff({
  mode = "power",
  disabled,
  busy,
  onRun,
}: {
  mode?: "power" | "finish" | "full";
  disabled?: boolean;
  busy?: string | null;
  onRun: (action: string, long: boolean) => void;
}) {
  const isFinish = mode === "finish" || mode === "full";
  const isPower = mode === "power" || mode === "full";

  return (
    <div className="fl-signoff">
      {isFinish && (
        <>
          <SignoffMatrixPanel busy={busy} onRun={onRun} showOrchestrator />
          <div className="fl-signoff-head">
            <strong>Azioni signoff timing / geometria / LVS</strong>
            <p>
              Docs{" "}
              <a href="/materiali/reference/signoff-matrix.md">signoff-matrix</a> ·{" "}
              <a href="/materiali/reference/golden-metrics.md">golden-metrics</a>
            </p>
          </div>
          <ActionGrid
            actions={FINISH_ACTIONS}
            disabled={disabled}
            busy={busy}
            onRun={onRun}
          />
        </>
      )}

      {isPower && (
        <>
          <div className="fl-signoff-head">
            <strong>Signoff power &amp; SPICE</strong>
            <p>
              Catena: VCD/activity → <strong>vectorless</strong> → chip mesh → vyges-em-ir →{" "}
              <strong>dynamic IR I(t)</strong> → System PDN. Docs{" "}
              <a href="/materiali/reference/spice-power-chain.md">spice-power-chain</a>
              {" · "}
              <a href="/materiali/reference/vectorless-power.md">vectorless-power</a>
              {" · "}
              <a href="/materiali/reference/vyges-em-ir.md">vyges-em-ir</a>
              {" · "}
              <a href="/materiali/reference/dynamic-ir.md">dynamic-ir</a>.
            </p>
          </div>
          <DynamicIrHeatmap />
          <ActionGrid
            actions={POWER_ACTIONS}
            disabled={disabled}
            busy={busy}
            onRun={onRun}
          />
          {(mode === "full") && (
            <>
              <div className="fl-signoff-head">
                <strong>Fase 2 · PKG &amp; thermal</strong>
                <p>
                  Proxy educativi ·{" "}
                  <a href="/materiali/reference/pkg-design-package.md">pkg-design-package</a>
                </p>
              </div>
              <ActionGrid
                actions={PHASE2_ACTIONS}
                disabled={disabled}
                busy={busy}
                onRun={onRun}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}

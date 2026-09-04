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
import { StaIrAwarePanel } from "./StaIrAwarePanel";
import { EcoPanel } from "./EcoPanel";
import { DynamicIrHeatmap } from "./DynamicIrHeatmap";
import { IrMeshLedger } from "./IrMeshLedger";

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
    hint: "VCD or synthetic · I_avg",
    icon: Activity,
    long: false,
  },
  {
    id: "vectorless",
    label: "Vectorless / dynamic",
    hint: "Najm P01 · IR without vectors",
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
    hint: "Apache-2.0 engine · CG + BE",
    icon: Zap,
    long: false,
  },
  {
    id: "dynamic_ir",
    label: "Dynamic IR I(t)",
    hint: "A DirectLU current_run · B SA-AMG · heatmap",
    icon: Zap,
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
    id: "power_signoff",
    label: "Power signoff",
    hint: "activity → chip IR → export + golden",
    icon: Zap,
    long: true,
  },
  {
    id: "gridcheck",
    label: "Gridcheck PDN",
    hint: "check_power_grid on floorplan PDN",
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
    id: "sta_ir_aware",
    label: "STA IR-aware",
    hint: "NLDM path × per-cell ITerm V",
    icon: Clock,
    long: false,
  },
  {
    id: "yosys_equiv",
    label: "Yosys equiv",
    hint: "RTL ↔ synth",
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
    hint: "OpenRCX SPEF",
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
    hint: "GDS vs filtered CDL · well→VDD/VSS",
    icon: ShieldCheck,
    long: true,
  },
  {
    id: "eco",
    label: "ECO propose",
    hint: "Post-finish plan. Apply refused on flowlab.",
    icon: Clock,
    long: false,
  },
  {
    id: "klayout_drc",
    label: "KLayout DRC (GDS only)",
    hint: "Legacy GDS DRC · prefer drc_signoff",
    icon: ShieldCheck,
    long: true,
  },
];

const PHASE2_ACTIONS: SignoffAction[] = [
  {
    id: "thermal_signoff",
    label: "Thermal (HotSpot)",
    hint: "Architecture compact model · °C",
    icon: Thermometer,
    long: false,
  },
  {
    id: "pkg_signoff",
    label: "PKG signoff",
    hint: "Bump + dummy rdl_route + system PDN",
    icon: Package,
    long: true,
  },
  {
    id: "system_pdn",
    label: "System PDN",
    hint: "VRM→board→pkg→die ngspice ladder",
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
    label: "PKG RDL (dummy)",
    hint: "sidecar rdl_route · dummy bump, not C4",
    icon: Package,
    long: false,
  },
  {
    id: "signoff_phase2",
    label: "Signoff Phase 2",
    hint: "HotSpot + PKG bump/RDL",
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
              <strong>{busy === s.id ? "Running…" : s.label}</strong>
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
  const showFinish = mode === "finish" || mode === "full";
  const showPower = mode === "power" || mode === "finish" || mode === "full";

  return (
    <div className="fl-signoff">
      <div className="fl-signoff-head">
        <strong>Loop</strong>
        <p>
          RTL → finish → <code>signoff_all</code> (STA · DRC · LVS · power).
          ECO apply writes <code>eco_scratch</code> and still requires
          that close. DSE only suggests knobs.
        </p>
      </div>
      {showFinish && (
        <div id="signoff">
          <SignoffMatrixPanel busy={busy} onRun={onRun} showOrchestrator />
          <EcoPanel busy={busy} onRun={onRun} />
          <StaIrAwarePanel busy={busy} onRun={onRun} />
          <details className="fl-signoff-more">
            <summary>Individual STA / DRC / LVS scripts</summary>
            <p>
              Docs{" "}
              <a href="/materials/reference/signoff-matrix.md">signoff-matrix</a> ·{" "}
              <a href="/materials/reference/golden-metrics.md">golden-metrics</a>
            </p>
            <ActionGrid
              actions={FINISH_ACTIONS}
              disabled={disabled}
              busy={busy}
              onRun={onRun}
            />
          </details>
        </div>
      )}

      {showPower && (
        <>
          <div className="fl-signoff-head" id="ir">
            <strong>Signoff power &amp; SPICE</strong>
            <p>
              Chip IR, Dynamic IR I(t), and the five-mesh ledger live here with
              the power pillar. System PDN / Phase 2 stay on{" "}
              <a href="/pkg">PKG</a>. Docs{" "}
              <a href="/materials/reference/spice-power-chain.md">spice-power-chain</a>
              {" · "}
              <a href="/materials/reference/dynamic-ir.md">dynamic-ir</a>.
            </p>
          </div>
          <IrMeshLedger />
          <DynamicIrHeatmap />
          <details className="fl-signoff-more">
            <summary>Individual power / SPICE scripts</summary>
            <ActionGrid
              actions={POWER_ACTIONS}
              disabled={disabled}
              busy={busy}
              onRun={onRun}
            />
          </details>
        </>
      )}

      {showFinish && (
        <p className="fl-signoff-lab">
          DSE proposes knobs on <a href="/lab">/lab</a>. It does not run{" "}
          <code>signoff_all</code>. Wins stay in <code>win_rule.py</code>.
        </p>
      )}

      {mode === "full" && (
        <details className="fl-signoff-more">
          <summary>Phase 2 · PKG &amp; thermal (educational proxies)</summary>
          <p>
            Docs{" "}
            <a href="/materials/reference/pkg-design-package.md">pkg-design-package</a>
          </p>
          <ActionGrid
            actions={PHASE2_ACTIONS}
            disabled={disabled}
            busy={busy}
            onRun={onRun}
          />
        </details>
      )}
    </div>
  );
}

/** Catena dati RTL → PKG: cosa produce/consuma ogni fase per power & SPICE. */

export type ChainNode = {
  phaseId: string;
  label: string;
  produces: string[];
  consumes: string[];
  spice?: string;
  doc?: string;
  action?: string;
};

export const POWER_CHAIN: ChainNode[] = [
  {
    phaseId: "rtl",
    label: "RTL",
    produces: ["gcd.vcd", "toggle activity (proxy)"],
    consumes: ["gcd.v"],
    spice: "—",
    doc: "/materiali/reference/spice-power-chain.md#1-rtl--attivit",
    action: "rtl_sim",
  },
  {
    phaseId: "synth",
    label: "Sintesi",
    produces: ["netlist gate-level", "area/celle Yosys"],
    consumes: ["RTL", "SDC", "liberty (.lib)"],
    doc: "/materiali/reference/spice-power-chain.md#2-liberty--celle",
  },
  {
    phaseId: "floorplan",
    label: "Floorplan",
    produces: ["2_4_floorplan_pdn.odb", "straps VDD/VSS (M5/M8)"],
    consumes: ["synth ODB", "util core"],
    doc: "/materiali/reference/spice-power-chain.md#3-floorplan--pdn",
    action: "floorplan",
  },
  {
    phaseId: "pdn",
    label: "PDN chip",
    produces: [".gridcheck_pdn.ok", "PSM-0040 connettività"],
    consumes: ["floorplan PDN ODB"],
    spice: "mesh R (dopo finish: write_pg_spice)",
    doc: "/materiali/reference/spice-chip-mesh.md",
    action: "gridcheck",
  },
  {
    phaseId: "place",
    label: "Place",
    produces: ["posizione celle → correnti locali"],
    consumes: ["floorplan", "density"],
    doc: "/materiali/reference/spice-power-chain.md#4-placement--correnti",
    action: "place",
  },
  {
    phaseId: "cts",
    label: "CTS",
    produces: ["buffer clock → switching extra"],
    consumes: ["placement"],
    action: "cts",
  },
  {
    phaseId: "route",
    label: "Route",
    produces: ["mesh IR paths", "SPEF"],
    consumes: ["CTS ODB"],
    action: "route",
  },
  {
    phaseId: "finish",
    label: "Finish",
    produces: ["6_final.odb", "report_power", "GDS/SPEF"],
    consumes: ["routed design"],
    doc: "/materiali/reference/spice-power-chain.md#5-finish--report_power",
    action: "finish",
  },
  {
    phaseId: "pkg",
    label: "PKG / System",
    produces: ["system_pdn_*.json", "Z(f)", "die droop"],
    consumes: ["I_die da activity/chip IR", "config ladder"],
    spice: "ngspice AC+TRAN",
    doc: "/materiali/reference/spice-ngspice-primer.md",
    action: "system_pdn",
  },
];

/** Analisi SPICE opzionali post-finish (non fasi pipeline). */
export const SPICE_ANALYSES = [
  {
    id: "activity_power",
    label: "Activity → power",
    produces: ["activity_power_*.log", "I_avg per System PDN"],
    spice: "— (liberty internal/leak/switch)",
    action: "activity_power",
  },
  {
    id: "chip_pdn_ir",
    label: "Chip IR mesh",
    produces: ["pg_vdd_bumps.sp", "pdn_chip_ir_*.json"],
    spice: "write_pg_spice + pdn_transient.py",
    doc: "/materiali/reference/spice-chip-mesh.md",
    action: "chip_pdn_ir",
  },
  {
    id: "power_chain",
    label: "Catena completa",
    produces: ["tutti i report + sim/spice/"],
    spice: "ngspice + mesh",
    action: "power_chain",
  },
] as const;

export function chainForPhase(phaseId: string): ChainNode | undefined {
  return POWER_CHAIN.find((n) => n.phaseId === phaseId);
}

/** Catena dati RTL → PKG: cosa produce/consuma ogni fase per power & SPICE. */

export type ChainNode = {
  phaseId: string;
  label: string;
  lessonIds: string[];
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
    lessonIds: ["00-intro"],
    produces: ["gcd.vcd", "toggle activity"],
    consumes: ["gcd.v"],
    spice: "VCD (→ activity futura)",
    doc: "/materiali/reference/spice-power-chain.md#lezione-00-intro",
    action: "rtl_sim",
  },
  {
    phaseId: "synth",
    label: "Sintesi",
    lessonIds: ["01-constraints", "02-synthesis"],
    produces: ["netlist gate-level", "celle .lib", "area Yosys"],
    consumes: ["RTL", "SDC", "liberty"],
    spice: "liberty → report_power",
    doc: "/materiali/reference/spice-power-chain.md#lezione-02-synthesis",
    action: "synth",
  },
  {
    phaseId: "floorplan",
    label: "Floorplan",
    lessonIds: ["03-floorplan"],
    produces: ["2_4_floorplan_pdn.odb", "straps VDD/VSS"],
    consumes: ["synth ODB", "util core"],
    spice: "pdngen (mesh R post-finish)",
    doc: "/materiali/reference/spice-power-chain.md#lezione-03-floorplan",
    action: "floorplan",
  },
  {
    phaseId: "pdn",
    label: "PDN chip",
    lessonIds: ["03-floorplan"],
    produces: [".gridcheck_pdn.ok", "PSM-0040"],
    consumes: ["2_4_floorplan_pdn.odb"],
    spice: "write_pg_spice (post finish)",
    doc: "/materiali/reference/spice-chip-mesh.md",
    action: "gridcheck",
  },
  {
    phaseId: "place",
    label: "Place",
    lessonIds: ["04-placement"],
    produces: ["ITermNode posizioni", "sink correnti"],
    consumes: ["floorplan ODB"],
    spice: "I per pin in mesh",
    doc: "/materiali/reference/spice-power-chain.md#lezione-04-placement",
    action: "place",
  },
  {
    phaseId: "cts",
    label: "CTS",
    lessonIds: ["05-cts"],
    produces: ["buffer clock", "↑ switching"],
    consumes: ["placement"],
    spice: "clock group in report_power",
    doc: "/materiali/reference/spice-power-chain.md#lezione-05-cts",
    action: "cts",
  },
  {
    phaseId: "route",
    label: "Route",
    lessonIds: ["06-routing"],
    produces: ["mesh routed", "SPEF (finish)"],
    consumes: ["CTS ODB"],
    spice: "IR su geom post-route",
    doc: "/materiali/reference/spice-power-chain.md#lezione-06-routing",
    action: "route",
  },
  {
    phaseId: "finish",
    label: "Finish",
    lessonIds: ["07-finish"],
    produces: ["6_final.odb", "report_power", "IR heatmap"],
    consumes: ["routed design"],
    spice: "PDNSim + activity log",
    doc: "/materiali/reference/spice-power-chain.md#lezione-07-finish",
    action: "finish",
  },
  {
    phaseId: "pkg",
    label: "PKG / System",
    lessonIds: ["07-finish"],
    produces: ["system_pdn_*.json", "Z(f)", "die droop"],
    consumes: ["I_die activity/chip IR", "default.json"],
    spice: "ngspice AC+TRAN",
    doc: "/materiali/reference/spice-ngspice-primer.md",
    action: "system_pdn",
  },
];

export const SPICE_ANALYSES = [
  {
    id: "activity_power",
    label: "Activity → power",
    produces: ["activity_power_*.log", "I_avg"],
    spice: "liberty leak/switch/internal",
    doc: "/materiali/reference/spice-power-chain.md#lezione-07-finish",
    action: "activity_power",
  },
  {
    id: "chip_pdn_ir",
    label: "Chip IR mesh",
    produces: ["pg_vdd_bumps.sp", "pdn_chip_ir_*.json"],
    spice: "write_pg_spice + pdn_transient",
    doc: "/materiali/reference/spice-chip-mesh.md",
    action: "chip_pdn_ir",
  },
  {
    id: "system_pdn",
    label: "System PDN",
    produces: ["system_pdn_*.json", "Z(f)", "droop"],
    spice: "ngspice ladder",
    doc: "/materiali/reference/spice-ngspice-primer.md",
    action: "system_pdn",
  },
  {
    id: "power_chain",
    label: "Catena completa",
    produces: ["tutti report", "sim/spice/"],
    spice: "ngspice + mesh + export",
    doc: "/materiali/reference/spice-power-chain.md",
    action: "power_chain",
  },
] as const;

export function chainForPhase(phaseId: string): ChainNode | undefined {
  return POWER_CHAIN.find((n) => n.phaseId === phaseId);
}

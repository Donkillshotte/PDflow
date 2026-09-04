/** Power / SPICE data chain: what each phase produces/consumes. PKG is not a signoff pillar. */

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
    produces: ["gcd.vcd", "gcd_gate.vcd", "toggle activity"],
    consumes: ["gcd.v", "6_final.v"],
    spice: "Gate VCD → activity_power name-join · RTL VCD for lesson 00",
    doc: "/materials/reference/spice-power-chain.md#lesson-00-intro",
    action: "gate_sim",
  },
  {
    phaseId: "synth",
    label: "Synth",
    lessonIds: ["01-constraints", "02-synthesis"],
    produces: ["gate-level netlist", ".lib cells", "Yosys area"],
    consumes: ["RTL", "SDC", "liberty"],
    spice: "liberty → report_power",
    doc: "/materials/reference/spice-power-chain.md#lesson-02-synthesis",
    action: "synth",
  },
  {
    phaseId: "floorplan",
    label: "Floorplan",
    lessonIds: ["03-floorplan"],
    produces: ["2_4_floorplan_pdn.odb", "straps VDD/VSS"],
    consumes: ["synth ODB", "util core"],
    spice: "pdngen (mesh R post-finish)",
    doc: "/materials/reference/spice-power-chain.md#lesson-03-floorplan",
    action: "floorplan",
  },
  {
    phaseId: "pdn",
    label: "PDN chip",
    lessonIds: ["03-floorplan"],
    produces: [".gridcheck_pdn.ok", "PSM-0040"],
    consumes: ["2_4_floorplan_pdn.odb"],
    spice: "write_pg_spice (post finish)",
    doc: "/materials/reference/spice-chip-mesh.md",
    action: "gridcheck",
  },
  {
    phaseId: "place",
    label: "Place",
    lessonIds: ["04-placement"],
    produces: ["ITermNode positions", "current sinks"],
    consumes: ["floorplan ODB"],
    spice: "I per pin in mesh",
    doc: "/materials/reference/spice-power-chain.md#lesson-04-placement",
    action: "place",
  },
  {
    phaseId: "cts",
    label: "CTS",
    lessonIds: ["05-cts"],
    produces: ["buffer clock", "↑ switching"],
    consumes: ["placement"],
    spice: "clock group in report_power",
    doc: "/materials/reference/spice-power-chain.md#lesson-05-cts",
    action: "cts",
  },
  {
    phaseId: "route",
    label: "Route",
    lessonIds: ["06-routing"],
    produces: ["mesh routed", "SPEF (finish)"],
    consumes: ["CTS ODB"],
    spice: "IR on post-route geometry",
    doc: "/materials/reference/spice-power-chain.md#lesson-06-routing",
    action: "route",
  },
  {
    phaseId: "finish",
    label: "Finish",
    lessonIds: ["07-finish"],
    produces: ["6_final.odb", "report_power", "IR heatmap", "sta/drc/lvs signoff JSON"],
    consumes: ["routed design"],
    spice: "PDNSim + signoff_all",
    doc: "/materials/reference/signoff-matrix.md",
    action: "signoff_all",
  },
  {
    phaseId: "pkg",
    label: "PKG / System",
    lessonIds: ["07-finish"],
    produces: ["system_pdn_*.json", "Z(f)", "die droop"],
    consumes: ["I_die activity/chip IR", "default.json"],
    spice: "ngspice AC+TRAN · pkg_signoff · HotSpot — on /pkg, not a FlowLab phase",
    doc: "/pkg",
    action: "system_pdn",
  },
];

export const SPICE_ANALYSES = [
  {
    id: "activity_power",
    label: "Activity → power",
    produces: ["activity_power_*.log", "I_avg"],
    spice: "liberty leak/switch/internal",
    doc: "/materials/reference/spice-power-chain.md#lesson-07-finish",
    action: "activity_power",
  },
  {
    id: "vectorless",
    label: "Vectorless / dynamic IR",
    produces: ["vectorless_*.json", "inst_power_map.json"],
    spice: "Najm P01 + Kouroussis envelope + PDNSim",
    doc: "/materials/reference/vectorless-power.md",
    action: "vectorless",
  },
  {
    id: "chip_pdn_ir",
    label: "Chip IR mesh",
    produces: ["pg_vdd_bumps.sp", "pdn_chip_ir_*.json"],
    spice: "write_pg_spice + pdn_transient",
    doc: "/materials/reference/spice-chip-mesh.md",
    action: "chip_pdn_ir",
  },
  {
    id: "vyges_em_ir",
    label: "vyges-em-ir",
    produces: ["vyges_em_ir_*.json", "gcd_*.pdn"],
    spice: "CG binary + backward Euler on the same mesh",
    doc: "/materials/reference/vyges-em-ir.md",
    action: "vyges_em_ir",
  },
  {
    id: "dynamic_ir",
    label: "Dynamic IR I(t)",
    produces: ["dynamic_ir_*.json", "dynamic_ir_*.svg"],
    spice: "per-ITerm PWL + Solver A LU + Solver B SA-AMG + heatmap",
    doc: "/materials/reference/dynamic-ir.md",
    action: "dynamic_ir",
  },
  {
    id: "system_pdn",
    label: "System PDN",
    produces: ["system_pdn_*.json", "Z(f)", "droop"],
    spice: "ngspice ladder",
    doc: "/materials/reference/spice-ngspice-primer.md",
    action: "system_pdn",
  },
  {
    id: "export_spice_lab",
    label: "Export SPICE lab",
    produces: ["sim/spice/*", "mesh_stats_*.json"],
    spice: "netlist + stats bundle",
    doc: "/materials/sim/spice/README.md",
    action: "export_spice_lab",
  },
  {
    id: "power_chain",
    label: "Full chain",
    produces: ["all reports", "sim/spice/"],
    spice: "ngspice + mesh + export",
    doc: "/materials/reference/spice-power-chain.md",
    action: "power_chain",
  },
  {
    id: "power_signoff",
    label: "Power signoff",
    produces: ["power_signoff_*.json"],
    spice: "gate golden IR/droop/Zmax",
    doc: "/materials/reference/signoff-matrix.md",
    action: "power_signoff",
  },
  {
    id: "thermal_signoff",
    label: "Thermal (HotSpot)",
    produces: ["thermal_signoff_*.json"],
    spice: "HotSpot t_max °C + IR+droop secondary",
    doc: "/materials/reference/signoff-matrix.md#phase-2-proxy",
    action: "thermal_signoff",
  },
  {
    id: "pkg_signoff",
    label: "PKG signoff",
    produces: ["pkg_bump_*.json", "pkg_rdl_*.json", "pkg_signoff_*.json"],
    spice: "bump config + dummy rdl_route + system PDN",
    doc: "/materials/reference/pkg-design-package.md",
    action: "pkg_signoff",
  },
] as const;

export function chainForPhase(phaseId: string): ChainNode | undefined {
  return POWER_CHAIN.find((n) => n.phaseId === phaseId);
}

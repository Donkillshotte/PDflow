/** Exhaustive mapping lessons 00–07 ↔ FlowLab ↔ SPICE (single source). */

export type LessonPowerLink = {
  lessonId: string;
  flowlabPhases: string[];
  anchor: string;
  title: string;
  summary: string;
  orfsArtifacts: string[];
  studioActions: string[];
  spiceOutputs: string[];
  docs: { href: string; label: string }[];
  flowlabHref?: string;
};

export const LESSON_POWER_LINKS: LessonPowerLink[] = [
  {
    lessonId: "00-intro",
    flowlabPhases: ["rtl"],
    anchor: "lesson-00-intro",
    title: "RTL and flow map",
    summary:
      "RTL sim produces the VCD: first link in the power chain (toggle → future activity).",
    orfsArtifacts: ["learn/flowlab/gcd.v", "learn/sim/gcd/gcd.vcd"],
    studioActions: ["rtl_sim"],
    spiceOutputs: [],
    docs: [
      { href: "/materials/reference/spice-power-chain.md#lesson-00-intro", label: "§00 RTL" },
      { href: "/materials/reference/file-formats.md", label: "Formats" },
    ],
    flowlabHref: "/flow?phase=rtl",
  },
  {
    lessonId: "01-constraints",
    flowlabPhases: ["synth"],
    anchor: "lesson-01-constraints",
    title: "SDC and clock",
    summary:
      "Clock constraints set frequency and duty: they indirectly affect switching power.",
    orfsArtifacts: ["constraint.sdc", "config.mk"],
    studioActions: ["synth"],
    spiceOutputs: [],
    docs: [
      { href: "/materials/reference/spice-power-chain.md#lesson-01-constraints", label: "§01 SDC" },
    ],
    flowlabHref: "/flow?phase=synth",
  },
  {
    lessonId: "02-synthesis",
    flowlabPhases: ["synth"],
    anchor: "lesson-02-synthesis",
    title: "Liberty and cells",
    summary:
      "Each .lib cell carries leakage/switching/internal power → basis for report_power and SPICE sinks.",
    orfsArtifacts: ["1_synth.v", "1_synth.odb", "NangateOpenCellLibrary_typical.lib"],
    studioActions: ["synth"],
    spiceOutputs: ["learn/sim/spice/nangate_inverter_demo.sp"],
    docs: [
      { href: "/materials/reference/spice-power-chain.md#lesson-02-synthesis", label: "§02 Liberty" },
      { href: "/materials/file/sim/spice/nangate_inverter_demo.sp", label: "Inverter SPICE demo" },
    ],
    flowlabHref: "/flow?phase=synth",
  },
  {
    lessonId: "03-floorplan",
    flowlabPhases: ["floorplan", "pdn"],
    anchor: "lesson-03-floorplan",
    title: "Floorplan and PDN straps",
    summary:
      "pdngen creates the VDD/VSS grid; gridcheck verifies connectivity before place.",
    orfsArtifacts: ["2_4_floorplan_pdn.odb", "grid_strategy-M1-M4-M7.tcl"],
    studioActions: ["floorplan", "gridcheck"],
    spiceOutputs: [],
    docs: [
      { href: "/materials/reference/spice-power-chain.md#lesson-03-floorplan", label: "§03 PDN" },
      { href: "/materials/reference/spice-chip-mesh.md", label: "Mesh SPICE (post-finish)" },
      { href: "/flow?phase=pdn", label: "FlowLab PDN" },
    ],
    flowlabHref: "/flow?phase=floorplan",
  },
  {
    lessonId: "04-placement",
    flowlabPhases: ["place"],
    anchor: "lesson-04-placement",
    title: "Placement and current sinks",
    summary:
      "Cell coordinates → ITermNode_* nodes in the write_pg_spice mesh.",
    orfsArtifacts: ["3_5_place_dp.odb", "3_place.odb"],
    studioActions: ["place"],
    spiceOutputs: ["pg_vdd_bumps.sp (post finish)"],
    docs: [
      { href: "/materials/reference/spice-power-chain.md#lesson-04-placement", label: "§04 Place" },
      { href: "/materials/reference/spice-chip-mesh.md#anatomy-of-pg_vdd_bumpssp", label: "ITermNode" },
    ],
    flowlabHref: "/flow?phase=place",
  },
  {
    lessonId: "05-cts",
    flowlabPhases: ["cts"],
    anchor: "lesson-05-cts",
    title: "CTS and clock switching",
    summary:
      "Clock buffers add capacitance and toggles → increase switching current in report_power.",
    orfsArtifacts: ["4_1_cts.odb", "4_cts.odb"],
    studioActions: ["cts"],
    spiceOutputs: [],
    docs: [
      { href: "/materials/reference/spice-power-chain.md#lesson-05-cts", label: "§05 CTS" },
    ],
    flowlabHref: "/flow?phase=cts",
  },
  {
    lessonId: "06-routing",
    flowlabPhases: ["route"],
    anchor: "lesson-06-routing",
    title: "Routing and SPEF",
    summary:
      "Net parasitics affect timing; route DRC feeds the geometry pillar of post-finish signoff.",
    orfsArtifacts: ["5_2_route.odb", "route.guide", "5_route_drc.rpt"],
    studioActions: ["route", "drc_signoff"],
    spiceOutputs: [],
    docs: [
      { href: "/materials/reference/spice-power-chain.md#lesson-06-routing", label: "§06 Route" },
      { href: "/materials/reference/signoff-matrix.md", label: "Signoff matrix (DRC)" },
    ],
    flowlabHref: "/flow?phase=route",
  },
  {
    lessonId: "07-finish",
    flowlabPhases: ["finish", "pkg"],
    anchor: "lesson-07-finish",
    title: "Finish, IR, and SPICE chain",
    summary:
      "report_power + analyze_power_grid → chip IR mesh + System PDN ngspice (signoff FlowLab).",
    orfsArtifacts: [
      "6_final.odb",
      "6_final.gds",
      "6_final.spef",
      "orfs_final_ir_drop.png",
    ],
    studioActions: [
      "finish",
      "sta_signoff",
      "drc_signoff",
      "klayout_lvs",
      "power_signoff",
      "signoff_all",
      "activity_power",
      "vectorless",
      "chip_pdn_ir",
      "vyges_em_ir",
      "dynamic_ir",
      "system_pdn",
      "power_chain",
      "yosys_equiv",
      "formal_gcd",
      "openrcx_report",
      "thermal_signoff",
      "pkg_signoff",
      "signoff_phase2",
    ],
    spiceOutputs: [
      "system_pdn_*.json",
      "pdn_chip_ir_*.json",
      "vyges_em_ir_*.json",
      "dynamic_ir_*.json",
      "learn/sim/spice/*",
    ],
    docs: [
      { href: "/materials/reference/spice-power-chain.md#lesson-07-finish", label: "§07 Finish" },
      { href: "/materials/reference/vectorless-power.md", label: "Vectorless / dynamic" },
      { href: "/materials/reference/vyges-em-ir.md", label: "vyges-em-ir" },
      { href: "/materials/reference/dynamic-ir.md", label: "Dynamic IR I(t)" },
      { href: "/materials/reference/oss-integrations.md", label: "OSS matrix" },
      { href: "/materials/reference/signoff-matrix.md", label: "Signoff matrix 4 pillars" },
      { href: "/materials/reference/spice-ngspice-primer.md", label: "ngspice" },
      { href: "/pkg", label: "Hub PKG" },
      { href: "/flow?phase=pkg", label: "FlowLab PKG" },
    ],
    flowlabHref: "/flow?phase=finish",
  },
];

export function powerLinkForLesson(lessonId: string): LessonPowerLink | undefined {
  return LESSON_POWER_LINKS.find((l) => l.lessonId === lessonId);
}

export function powerLinkForPhase(phaseId: string): LessonPowerLink[] {
  return LESSON_POWER_LINKS.filter((l) => l.flowlabPhases.includes(phaseId));
}

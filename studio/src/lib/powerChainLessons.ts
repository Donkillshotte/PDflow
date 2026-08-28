/** Collegamento esaustivo lezioni 00–07 ↔ FlowLab ↔ SPICE (single source). */

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
    anchor: "lezione-00-intro",
    title: "RTL e mappa del flusso",
    summary:
      "La sim RTL produce il VCD: primo anello della catena power (toggle → activity futura).",
    orfsArtifacts: ["learn/flowlab/gcd.v", "learn/sim/gcd/gcd.vcd"],
    studioActions: ["rtl_sim"],
    spiceOutputs: [],
    docs: [
      { href: "/materiali/reference/spice-power-chain.md#lezione-00-intro", label: "§00 RTL" },
      { href: "/materiali/reference/file-formats.md", label: "Formati" },
    ],
    flowlabHref: "/flusso?phase=rtl",
  },
  {
    lessonId: "01-constraints",
    flowlabPhases: ["synth"],
    anchor: "lezione-01-constraints",
    title: "SDC e clock",
    summary:
      "I vincoli di clock determinano frequenza e duty: influenzano switching power indirettamente.",
    orfsArtifacts: ["constraint.sdc", "config.mk"],
    studioActions: ["synth"],
    spiceOutputs: [],
    docs: [
      { href: "/materiali/reference/spice-power-chain.md#lezione-01-constraints", label: "§01 SDC" },
    ],
    flowlabHref: "/flusso?phase=synth",
  },
  {
    lessonId: "02-synthesis",
    flowlabPhases: ["synth"],
    anchor: "lezione-02-synthesis",
    title: "Liberty e celle",
    summary:
      "Ogni cella .lib porta leakage/switching/internal power → base di report_power e sink SPICE.",
    orfsArtifacts: ["1_synth.v", "1_synth.odb", "NangateOpenCellLibrary_typical.lib"],
    studioActions: ["synth"],
    spiceOutputs: ["learn/sim/spice/nangate_inverter_demo.sp"],
    docs: [
      { href: "/materiali/reference/spice-power-chain.md#lezione-02-synthesis", label: "§02 Liberty" },
      { href: "/materiali/file/sim/spice/nangate_inverter_demo.sp", label: "Inverter SPICE demo" },
    ],
    flowlabHref: "/flusso?phase=synth",
  },
  {
    lessonId: "03-floorplan",
    flowlabPhases: ["floorplan", "pdn"],
    anchor: "lezione-03-floorplan",
    title: "Floorplan e PDN straps",
    summary:
      "pdngen crea la griglia VDD/VSS; gridcheck verifica connettività prima del place.",
    orfsArtifacts: ["2_4_floorplan_pdn.odb", "grid_strategy-M1-M4-M7.tcl"],
    studioActions: ["floorplan", "gridcheck"],
    spiceOutputs: [],
    docs: [
      { href: "/materiali/reference/spice-power-chain.md#lezione-03-floorplan", label: "§03 PDN" },
      { href: "/materiali/reference/spice-chip-mesh.md", label: "Mesh SPICE (post-finish)" },
      { href: "/flusso?phase=pdn", label: "FlowLab PDN" },
    ],
    flowlabHref: "/flusso?phase=floorplan",
  },
  {
    lessonId: "04-placement",
    flowlabPhases: ["place"],
    anchor: "lezione-04-placement",
    title: "Placement e sink di corrente",
    summary:
      "Coordinate celle → nodi ITermNode_* nella mesh write_pg_spice.",
    orfsArtifacts: ["3_5_place_dp.odb", "3_place.odb"],
    studioActions: ["place"],
    spiceOutputs: ["pg_vdd_bumps.sp (post finish)"],
    docs: [
      { href: "/materiali/reference/spice-power-chain.md#lezione-04-placement", label: "§04 Place" },
      { href: "/materiali/reference/spice-chip-mesh.md#anatomia-di-pg_vdd_bumpssp", label: "ITermNode" },
    ],
    flowlabHref: "/flusso?phase=place",
  },
  {
    lessonId: "05-cts",
    flowlabPhases: ["cts"],
    anchor: "lezione-05-cts",
    title: "CTS e switching clock",
    summary:
      "Buffer clock aggiungono capacità e toggle → aumentano corrente di switching nel report_power.",
    orfsArtifacts: ["4_1_cts.odb", "4_cts.odb"],
    studioActions: ["cts"],
    spiceOutputs: [],
    docs: [
      { href: "/materiali/reference/spice-power-chain.md#lezione-05-cts", label: "§05 CTS" },
    ],
    flowlabHref: "/flusso?phase=cts",
  },
  {
    lessonId: "06-routing",
    flowlabPhases: ["route"],
    anchor: "lezione-06-routing",
    title: "Routing e SPEF",
    summary:
      "Parassiti di rete influenzano timing; route DRC alimenta il pilastro geometria del signoff post-finish.",
    orfsArtifacts: ["5_2_route.odb", "route.guide", "5_route_drc.rpt"],
    studioActions: ["route", "drc_signoff"],
    spiceOutputs: [],
    docs: [
      { href: "/materiali/reference/spice-power-chain.md#lezione-06-routing", label: "§06 Route" },
      { href: "/materiali/reference/signoff-matrix.md", label: "Matrice signoff (DRC)" },
    ],
    flowlabHref: "/flusso?phase=route",
  },
  {
    lessonId: "07-finish",
    flowlabPhases: ["finish", "pkg"],
    anchor: "lezione-07-finish",
    title: "Finish, IR e catena SPICE",
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
      "chip_pdn_ir",
      "system_pdn",
      "power_chain",
      "thermal_signoff",
      "pkg_signoff",
      "signoff_phase2",
    ],
    spiceOutputs: [
      "system_pdn_*.json",
      "pdn_chip_ir_*.json",
      "learn/sim/spice/*",
    ],
    docs: [
      { href: "/materiali/reference/spice-power-chain.md#lezione-07-finish", label: "§07 Finish" },
      { href: "/materiali/reference/signoff-matrix.md", label: "Matrice signoff 4 pilastri" },
      { href: "/materiali/reference/spice-ngspice-primer.md", label: "ngspice" },
      { href: "/pkg", label: "Hub PKG" },
      { href: "/flusso?phase=pkg", label: "FlowLab PKG" },
    ],
    flowlabHref: "/flusso?phase=finish",
  },
];

export function powerLinkForLesson(lessonId: string): LessonPowerLink | undefined {
  return LESSON_POWER_LINKS.find((l) => l.lessonId === lessonId);
}

export function powerLinkForPhase(phaseId: string): LessonPowerLink[] {
  return LESSON_POWER_LINKS.filter((l) => l.flowlabPhases.includes(phaseId));
}

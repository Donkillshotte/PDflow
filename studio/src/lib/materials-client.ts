/** Client-safe material catalog (no fs). */

export type MaterialLink = {
  href: string;
  title: string;
  group: string;
  description: string;
};

export const MATERIALS: MaterialLink[] = [
  {
    href: "/materiali/reference/golden-metrics.md",
    title: "Metriche d’oro",
    group: "Riferimento",
    description: "WNS, period_min, area del run learn di riferimento.",
  },
  {
    href: "/materiali/reference/gui-atlas.md",
    title: "Atlante GUI",
    group: "GUI",
    description: "Screenshot Qt pixel-level, anatomia A–G, layer M2/M3.",
  },
  {
    href: "/materiali/reference/debug-playbook.md",
    title: "Debug playbook",
    group: "Riferimento",
    description: "DPL-0038, RSZ-0062, STA-2204 e checklist pre-run.",
  },
  {
    href: "/materiali/reference/glossary.md",
    title: "Glossario",
    group: "Riferimento",
    description: "Termini PD: skew, NDR, gcell, OpenRCX, IFP-0028.",
  },
  {
    href: "/materiali/reference/file-formats.md",
    title: "Formati file",
    group: "Riferimento",
    description: "ODB, SPEF, DEF, GDS, route.guide — cosa aprire e perché.",
  },
  {
    href: "/materiali/reference/tool-hooks.md",
    title: "Tool hooks",
    group: "Riferimento",
    description: "OpenROAD -web/-python/-metrics, OpenSTA JSON, Yosys, KLayout.",
  },
  {
    href: "/materiali/reference/extended-flow.md",
    title: "Flusso esteso",
    group: "Riferimento",
    description: "RTL sim, activity, DRC, gridcheck, PDN, bump/RDL, thermal — mappa READY/MISSING.",
  },
  {
    href: "/materiali/workbook/quiz.md",
    title: "Quiz",
    group: "Workbook",
    description: "Autovalutazione per lezione + quiz GUI.",
  },
  {
    href: "/materiali/workbook/solutions.md",
    title: "Soluzioni",
    group: "Workbook",
    description: "Confronta dopo aver provato — numeri del run d’oro.",
  },
  {
    href: "/materiali/workbook/progetto-finale-template.md",
    title: "Progetto finale",
    group: "Workbook",
    description: "Template consegna lezione 07 con scarto vs golden-metrics.",
  },
  {
    href: "/materiali/CURRICULUM.md",
    title: "Syllabus",
    group: "Corso",
    description: "Piano 20–28 ore, obiettivi per lezione.",
  },
];

export const WALKTHROUGHS = [
  "walkthrough-synth.tcl.md",
  "walkthrough-floorplan.tcl.md",
  "walkthrough-global_place.tcl.md",
  "walkthrough-cts.tcl.md",
  "walkthrough-route.tcl.md",
  "walkthrough-finish.tcl.md",
].map((f) => ({
  href: `/materiali/reference/${f}`,
  title: f.replace("walkthrough-", "").replace(".tcl.md", ""),
  group: "Tcl",
  description: `Walkthrough annotato ${f}`,
}));

/** Shared material catalog (client + server safe — no fs). */

export type MaterialLink = {
  href: string;
  title: string;
  group: string;
  description: string;
};

export const MATERIALS: MaterialLink[] = [
  {
    href: "/materiali/reference/oss-integrations.md",
    title: "Integrazioni OSS",
    group: "Riferimento",
    description: "Stack integrato, gap commerciali, Magic/Netgen, vectorless.",
  },
  {
    href: "/materiali/reference/signoff-matrix.md",
    title: "Matrice signoff",
    group: "Riferimento",
    description: "4 pilastri STA/DRC/LVS/power · golden-gcd · gate PASS/FAIL.",
  },
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
    description: "RTL sim, activity, vectorless, DRC, gridcheck, PDN, bump/RDL, thermal.",
  },
  {
    href: "/materiali/reference/vectorless-power.md",
    title: "Vectorless / dynamic IR",
    group: "Riferimento",
    description: "Najm 1994 + Kouroussis DAC 2003 implementati sul GCD Nangate45.",
  },
  {
    href: "/materiali/reference/system-pdn.md",
    title: "System PDN",
    group: "Packaging",
    description: "ngspice hierarchical: VRM → board → package → die · Z(f) + load-step.",
  },
  {
    href: "/materiali/reference/spice-power-chain.md",
    title: "Catena SPICE RTL→PKG",
    group: "Packaging",
    description: "Collegamento tutte le fasi: VCD, liberty, mesh, ngspice ladder.",
  },
  {
    href: "/materiali/reference/spice-ngspice-primer.md",
    title: "ngspice · System PDN",
    group: "Packaging",
    description: "Leggere netlist TRAN/AC, interpretare Z(f) e droop.",
  },
  {
    href: "/materiali/reference/spice-chip-mesh.md",
    title: "SPICE chip mesh",
    group: "Packaging",
    description: "write_pg_spice, nodi ITerm, correnti celle, pdn_transient.",
  },
  {
    href: "/materiali/sim/spice/README.md",
    title: "Lab netlist SPICE",
    group: "Packaging",
    description: "Netlist demo e export pg_vdd_bumps / system_pdn.",
  },
  {
    href: "/materiali/file/sim/spice/nangate_inverter_demo.sp",
    title: "Demo inverter SPICE",
    group: "Packaging",
    description: "Netlist transistor-level educativa (Nangate-style).",
  },
  {
    href: "/materiali/reference/pkg-design-package.md",
    title: "PKG · design package",
    group: "Packaging",
    description: "Bump, RDL, C4, checklist design package e limiti Nangate45.",
  },
  {
    href: "/pkg",
    title: "Sezione PKG (hub)",
    group: "Packaging",
    description: "Hub UI: fasi PDN/PKG, docs e checklist consegna.",
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
] as const;

/** Resolve learn-relative path for SPICE/lab files linked from UI. */
export function spiceFileHref(rel: string): string {
  const cleaned = rel.replace(/^learn\//, "").replace(/^\//, "");
  return `/materiali/file/${cleaned}`;
}

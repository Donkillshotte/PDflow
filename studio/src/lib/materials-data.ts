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
    group: "Reference",
    description: "Stack integrato, gap commerciali, Magic/Netgen, vectorless, vyges-em-ir, dynamic IR.",
  },
  {
    href: "/materiali/reference/vyges-em-ir.md",
    title: "vyges-em-ir",
    group: "Reference",
    description: "Apache-2.0 IR/EM engine on the GCD PDNSim mesh.",
  },
  {
    href: "/materiali/reference/dynamic-ir.md",
    title: "Dynamic IR I(t)",
    group: "Reference",
    description: "PWL per pin, backward Euler, waveform and heatmap on GCD.",
  },
  {
    href: "/materiali/reference/dse.md",
    title: "DSE fisico-aware",
    group: "Reference",
    description: "E-graph datapath, BOiLS SSK-GP, Pareto by level, Dynamic IR oracle.",
  },
  {
    href: "/materiali/reference/dynamic-ir-landscape.md",
    title: "Landscape Dynamic IR",
    group: "Reference",
    description: "PDNSim, vyges, EMSim, ngspice — what is OSS and what is not.",
  },
  {
    href: "/materiali/reference/signoff-matrix.md",
    title: "Signoff matrix",
    group: "Reference",
    description: "4 pillars STA/DRC/LVS/power · golden-gcd · gate PASS/FAIL.",
  },
  {
    href: "/materiali/reference/golden-metrics.md",
    title: "Metrics d’oro",
    group: "Reference",
    description: "WNS, period_min, area of the reference learn run.",
  },
  {
    href: "/materiali/reference/gui-atlas.md",
    title: "Atlante GUI",
    group: "GUI",
    description: "Qt pixel-level screenshots, anatomy A–G, layer M2/M3.",
  },
  {
    href: "/materiali/reference/debug-playbook.md",
    title: "Debug playbook",
    group: "Reference",
    description: "DPL-0038, RSZ-0062, STA-2204 e checklist pre-run.",
  },
  {
    href: "/materiali/reference/glossary.md",
    title: "Glossary",
    group: "Reference",
    description: "PD terms: skew, NDR, gcell, OpenRCX, IFP-0028.",
  },
  {
    href: "/materiali/reference/file-formats.md",
    title: "File formats",
    group: "Reference",
    description: "ODB, SPEF, DEF, GDS, route.guide — what to open and why.",
  },
  {
    href: "/materiali/reference/tool-hooks.md",
    title: "Tool hooks",
    group: "Reference",
    description: "OpenROAD -web/-python/-metrics, OpenSTA JSON, Yosys, KLayout.",
  },
  {
    href: "/materiali/reference/extended-flow.md",
    title: "Extended flow",
    group: "Reference",
    description: "RTL sim, activity, vectorless, DRC, gridcheck, PDN, bump/RDL, thermal.",
  },
  {
    href: "/materiali/reference/vectorless-power.md",
    title: "Vectorless / dynamic IR",
    group: "Reference",
    description: "Najm 1994 + Kouroussis DAC 2003 implemented on GCD Nangate45.",
  },
  {
    href: "/materiali/reference/system-pdn.md",
    title: "System PDN",
    group: "Packaging",
    description: "ngspice hierarchical: VRM → board → package → die · Z(f) + load-step.",
  },
  {
    href: "/materiali/reference/spice-power-chain.md",
    title: "SPICE chain RTL→PKG",
    group: "Packaging",
    description: "Links all phases: VCD, liberty, mesh, ngspice ladder.",
  },
  {
    href: "/materiali/reference/spice-ngspice-primer.md",
    title: "ngspice · System PDN",
    group: "Packaging",
    description: "Read TRAN/AC netlists, interpret Z(f) and droop.",
  },
  {
    href: "/materiali/reference/spice-chip-mesh.md",
    title: "SPICE chip mesh",
    group: "Packaging",
    description: "write_pg_spice, ITerm nodes, cell currents, pdn_transient.",
  },
  {
    href: "/materiali/sim/spice/README.md",
    title: "SPICE lab netlist",
    group: "Packaging",
    description: "Demo netlist and export pg_vdd_bumps / system_pdn.",
  },
  {
    href: "/materiali/file/sim/spice/nangate_inverter_demo.sp",
    title: "Demo inverter SPICE",
    group: "Packaging",
    description: "Educational transistor-level netlist (Nangate-style).",
  },
  {
    href: "/materiali/reference/pkg-design-package.md",
    title: "PKG · design package",
    group: "Packaging",
    description: "Bump, RDL, C4, design package checklist and Nangate45 limits.",
  },
  {
    href: "/pkg",
    title: "PKG section (hub)",
    group: "Packaging",
    description: "UI hub: PDN/PKG phases, docs and delivery checklist.",
  },
  {
    href: "/materiali/workbook/quiz.md",
    title: "Quiz",
    group: "Workbook",
    description: "Self-assessment per lesson + GUI quiz.",
  },
  {
    href: "/materiali/workbook/solutions.md",
    title: "Solutions",
    group: "Workbook",
    description: "Compare after trying — numbers from the golden run.",
  },
  {
    href: "/materiali/workbook/progetto-finale-template.md",
    title: "Final project",
    group: "Workbook",
    description: "Lesson 07 delivery template with delta vs golden-metrics.",
  },
  {
    href: "/materiali/CURRICULUM.md",
    title: "Syllabus",
    group: "Course",
    description: "20–28 hour plan, objectives per lesson.",
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

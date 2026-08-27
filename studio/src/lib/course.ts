import fs from "fs";
import path from "path";

export const REPO_ROOT = path.resolve(process.cwd(), "..");
export const LEARN_ROOT = path.join(REPO_ROOT, "learn");
export const SCRIPTS_ROOT = path.join(REPO_ROOT, "scripts");

export type LessonMeta = {
  id: string;
  num: string;
  title: string;
  duration: string;
  stage: string;
  blurb: string;
  makeTarget: string;
};

export const LESSONS: LessonMeta[] = [
  {
    id: "00-intro",
    num: "00",
    title: "Introduzione",
    duration: "45–60 min",
    stage: "mappa",
    blurb: "RTL→GDS, cartelle ORFS, Desktop vs Preview, primo smoke synth.",
    makeTarget: "synth",
  },
  {
    id: "01-constraints",
    num: "01",
    title: "Constraints",
    duration: "60–90 min",
    stage: "SDC",
    blurb: "create_clock, I/O delay, config.mk, sweep relaxed/tight.",
    makeTarget: "place",
  },
  {
    id: "02-synthesis",
    num: "02",
    title: "Synthesis",
    duration: "45–75 min",
    stage: "Yosys",
    blurb: "Netlist gate-level, synth_stat, 1_synth.odb senza die.",
    makeTarget: "synth",
  },
  {
    id: "03-floorplan",
    num: "03",
    title: "Floorplan",
    duration: "60–90 min",
    stage: "die/PDN",
    blurb: "Core utilization, rows, power grid M1–M4–M7.",
    makeTarget: "floorplan",
  },
  {
    id: "04-placement",
    num: "04",
    title: "Placement",
    duration: "75–90 min",
    stage: "GP→DP",
    blurb: "Global vs detailed, resizer, overflow, buffer timing.",
    makeTarget: "place",
  },
  {
    id: "05-cts",
    num: "05",
    title: "CTS",
    duration: "60–90 min",
    stage: "clock",
    blurb: "Albero clock, skew, RSZ-0062 vs DPL-0038.",
    makeTarget: "cts",
  },
  {
    id: "06-routing",
    num: "06",
    title: "Routing",
    duration: "75–90 min",
    stage: "GRT/DRT",
    blurb: "Guide, wire M2/M3, DRC, congestion.",
    makeTarget: "route",
  },
  {
    id: "07-finish",
    num: "07",
    title: "Finish",
    duration: "60–90 min",
    stage: "GDS",
    blurb: "SPEF, signoff, period_min vs SDC, progetto finale.",
    makeTarget: "finish",
  },
];

export type ProgressData = {
  started_at?: string;
  completed_lessons: string[];
  last_lesson: string | null;
  notes?: string[];
  updated_at?: string;
  /** Per-lesson guided wizard: which steps are done */
  lesson_steps?: Record<string, string[]>;
  /** Interactive LAB checklist keys */
  lab_checks?: Record<string, string[]>;
};

export function progressPath() {
  return path.join(LEARN_ROOT, ".progress.json");
}

export function readProgress(): ProgressData {
  const p = progressPath();
  if (!fs.existsSync(p)) {
    return { completed_lessons: [], last_lesson: null };
  }
  return JSON.parse(fs.readFileSync(p, "utf8")) as ProgressData;
}

export function writeProgress(data: ProgressData) {
  fs.writeFileSync(progressPath(), JSON.stringify(data, null, 2) + "\n");
}

export function markLessonComplete(id: string) {
  const data = readProgress();
  const done = new Set(data.completed_lessons ?? []);
  done.add(id);
  data.completed_lessons = [...done].sort();
  data.last_lesson = id;
  data.updated_at = new Date().toISOString();
  if (!data.started_at) data.started_at = data.updated_at;
  writeProgress(data);
  return data;
}

export function updateLessonSteps(id: string, steps: string[]) {
  const data = readProgress();
  data.lesson_steps = { ...(data.lesson_steps ?? {}), [id]: steps };
  data.updated_at = new Date().toISOString();
  if (!data.started_at) data.started_at = data.updated_at;
  writeProgress(data);
  return data;
}

export function updateLabChecks(id: string, checks: string[]) {
  const data = readProgress();
  data.lab_checks = { ...(data.lab_checks ?? {}), [id]: checks };
  data.updated_at = new Date().toISOString();
  writeProgress(data);
  return data;
}

/** Extract checklist-worthy items from LAB markdown (- [ ] lines or ## Parte headings). */
export function extractLabChecklist(labMd: string): { id: string; label: string }[] {
  const items: { id: string; label: string }[] = [];
  const seen = new Set<string>();
  for (const line of labMd.split("\n")) {
    const check = line.match(/^- \[[ xX]\]\s+(.+)/);
    const parte = line.match(/^##\s+(Parte\s+\d+[^\n]*)/i);
    const label = (check?.[1] || parte?.[1] || "").trim();
    if (!label || label.length < 4) continue;
    const id = label
      .toLowerCase()
      .replace(/[^a-z0-9àèéìòù]+/gi, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 64);
    if (seen.has(id)) continue;
    seen.add(id);
    items.push({ id, label: label.slice(0, 120) });
    if (items.length >= 12) break;
  }
  return items;
}

export function lessonDir(id: string) {
  return path.join(LEARN_ROOT, "lessons", id);
}

export function readLessonFile(id: string, name: "README.md" | "LAB.md" | "run.sh") {
  const file = path.join(lessonDir(id), name);
  if (!fs.existsSync(file)) return null;
  return fs.readFileSync(file, "utf8");
}

const ALLOWED_CONTENT_PREFIXES = [
  "lessons/",
  "reference/",
  "workbook/",
  "README.md",
  "CURRICULUM.md",
  "AUDIT.md",
  "EVIDENCE.md",
];

export function resolveLearnContent(rel: string) {
  const cleaned = rel.replace(/^\/+/, "").replace(/\.\./g, "");
  if (!ALLOWED_CONTENT_PREFIXES.some((p) => cleaned === p || cleaned.startsWith(p))) {
    return null;
  }
  const abs = path.join(LEARN_ROOT, cleaned);
  if (!abs.startsWith(LEARN_ROOT) || !fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
    return null;
  }
  return abs;
}

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
    href: "/materiali/reference/system-pdn.md",
    title: "System PDN",
    group: "Packaging",
    description: "analyze_power_grid STRAPS · FULL · BUMPS — IR package/board proxy.",
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
].map((f) => ({
  href: `/materiali/reference/${f}`,
  title: f.replace("walkthrough-", "").replace(".tcl.md", ""),
  group: "Tcl",
  description: `Walkthrough annotato ${f}`,
}));

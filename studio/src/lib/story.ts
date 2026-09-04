/**
 * One snapshot for the three surfaces. Product wins stay in win_rule.py;
 * this module only reads artifacts and mirrors the published rule for UI.
 */
import fs from "fs";
import path from "path";
import { LEARN_ROOT, LESSONS, readProgress } from "./course";
import { collectStageResults } from "./results";
import { evaluateSignoffGates, leftoverSetupOpenDetail } from "./signoff";
import { leftoverNamedBit } from "./leftoverCatalog";
import { PIPELINE_STAGES } from "./jobs";

export const STORY_VARIANT = "flowlab";
export const IR_GOLD_MV = 45.298;

export { leftoverNamedBit };

const SLACK_PS = 5.0;
const METRIC_FRAC = 0.1;
const AREA_FRAC = 0.02;
const FLOORPLAN_TAGS = ["core_tighter", "core_looser", "aspect_wide"];

const OFFICIAL_SLOTS: { id: string; clockNs: number }[] = [
  { id: "gcd", clockNs: 0.46 },
  { id: "spi", clockNs: 1.0 },
  { id: "ibex", clockNs: 2.2 },
  { id: "aes", clockNs: 0.82 },
  { id: "dynamic_node", clockNs: 6.0 },
];

export type CampRow = {
  id?: string;
  design?: string;
  clock_ns?: number;
  role?: string;
  status?: string;
  variant?: string;
  finish_wns_ns?: number | null;
  stdcell_um2?: number | null;
  power_w?: number | null;
  leakage_w?: number | null;
  ir_drop_v?: number | null;
  ir_mean_v?: number | null;
  die_um2?: number | null;
  core_um2?: number | null;
  notes?: string;
  created_at?: number;
  extra?: { recipe?: string; title?: string; tag?: string };
};

export type StorySurfaceId = "course" | "lab" | "product";

export type StoryStep = {
  id: string;
  label: string;
  href: string;
  ready: boolean;
  detail: string;
};

export type StorySlot = {
  id: string;
  clockNs: number;
  baseWnsPs: number | null;
  wins: number;
  cooks: number;
};

export type ProductStory = {
  title: string;
  lead: string;
  variant: string;
  surfaces: {
    id: StorySurfaceId;
    label: string;
    href: string;
    ready: boolean;
    detail: string;
  }[];
  path: StoryStep[];
  pipeline: {
    ready: number;
    total: number;
    finishReady: boolean;
  };
  signoff: {
    ok: boolean | null;
    passed: number;
    total: number;
    detail: string;
  };
  ir: {
    goldMv: number;
    currentMv: number | null;
    goldPresent: boolean;
    currentPresent: boolean;
    detail: string;
  };
  staIr: {
    ready: boolean;
    slackNs: number | null;
    slackIrNs: number | null;
    nJoined: number | null;
    nGates: number | null;
    detail: string;
  };
  product: {
    slots: StorySlot[];
    wins: number;
    cooks: number;
    detail: string;
  };
  course: {
    done: number;
    total: number;
    nextId: string | null;
    nextTitle: string | null;
  };
};

function num(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function imp(next: number | null, old: number | null): number | null {
  if (next == null || old == null) return null;
  if (Math.abs(old) < 1e-18) return null;
  return ((old - next) / Math.abs(old)) * 100;
}

function movesFloorplan(cand: CampRow, base: CampRow): boolean {
  const variant = String(cand.variant || "");
  if (FLOORPLAN_TAGS.some((t) => variant.includes(t))) return true;
  for (const field of ["die_um2", "core_um2"] as const) {
    const next = num(cand[field]);
    const old = num(base[field]);
    if (next == null || old == null || Math.abs(old) < 1e-9) continue;
    if (Math.abs(next - old) / Math.abs(old) > AREA_FRAC) return true;
  }
  return false;
}

/** UI mirror of learn/dse/win_rule.py verdict(). */
export function productVerdict(cand: CampRow, base: CampRow): string {
  const cw = num(cand.finish_wns_ns);
  const bw = num(base.finish_wns_ns);
  if (cw == null || bw == null) return "incomplete";
  if (movesFloorplan(cand, base)) return "wrong_die";
  const dwPs = (cw - bw) * 1000;
  const cClosed = cw >= 0;
  const bClosed = bw >= 0;
  const area = imp(num(cand.stdcell_um2), num(base.stdcell_um2));
  const power = imp(num(cand.power_w), num(base.power_w));
  const leak = imp(num(cand.leakage_w), num(base.leakage_w));
  const ir = imp(num(cand.ir_drop_v), num(base.ir_drop_v));
  const worse =
    (area != null && area <= -METRIC_FRAC * 100) ||
    (power != null && power <= -METRIC_FRAC * 100) ||
    (leak != null && leak <= -METRIC_FRAC * 100) ||
    (ir != null && ir <= -METRIC_FRAC * 100);
  const better =
    (area != null && area >= METRIC_FRAC * 100) ||
    (power != null && power >= METRIC_FRAC * 100) ||
    (leak != null && leak >= METRIC_FRAC * 100) ||
    (ir != null && ir >= METRIC_FRAC * 100);
  if (cClosed && !bClosed && !worse) return "win";
  if (bClosed && !cClosed) return "lose";
  if (worse) return "lose";
  if (dwPs > SLACK_PS || (dwPs >= -SLACK_PS && better)) return "win";
  if (dwPs >= -SLACK_PS) return "tie";
  return "lose";
}

function readJsonl(rel: string): CampRow[] {
  const p = path.join(LEARN_ROOT, rel);
  if (!fs.existsSync(p)) return [];
  const rows: CampRow[] = [];
  for (const line of fs.readFileSync(p, "utf8").split("\n")) {
    const t = line.trim();
    if (!t) continue;
    try {
      rows.push(JSON.parse(t) as CampRow);
    } catch {
      /* skip */
    }
  }
  return rows;
}

function readReport(name: string): Record<string, unknown> | null {
  return readReportFile(`${name}_${STORY_VARIANT}.json`);
}

function readReportFile(fileName: string): Record<string, unknown> | null {
  const p = path.join(LEARN_ROOT, "sim/reports", fileName);
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** current_run I(t) from _direct.json. Never the locked gold teacher. */
export function readCurrentRunDroopMv(variant = STORY_VARIANT): number | null {
  const currentRun = readReportFile(`dynamic_ir_${variant}_direct.json`);
  if (!currentRun || currentRun.gold === true) return null;
  const top = num(currentRun.worst_droop_mv);
  if (top != null) return top;
  const dyn = currentRun.dynamic as { worst_droop?: number; worst_droop_mv?: number } | undefined;
  if (dyn?.worst_droop_mv != null) return num(dyn.worst_droop_mv);
  return dyn?.worst_droop != null ? Number(dyn.worst_droop) * 1e3 : null;
}

function summarizeProduct(rows: CampRow[]): ProductStory["product"] {
  const slots: StorySlot[] = OFFICIAL_SLOTS.map((slot) => {
    const same = rows.filter(
      (r) => r.design === slot.id && Math.abs(Number(r.clock_ns) - slot.clockNs) < 1e-6,
    );
    const base =
      same.find((r) => r.role === "base" && r.status === "done") ??
      same.find((r) => r.role === "base");
    const cooks = same.filter((r) => r.status === "done" && r.finish_wns_ns != null).length;
    let wins = 0;
    if (base) {
      for (const r of same) {
        if (r === base || r.role === "base") continue;
        if (r.status !== "done" || r.finish_wns_ns == null) continue;
        if (productVerdict(r, base) === "win") wins += 1;
      }
    }
    return {
      id: slot.id,
      clockNs: slot.clockNs,
      baseWnsPs: base?.finish_wns_ns != null ? Math.round(Number(base.finish_wns_ns) * 1000) : null,
      wins,
      cooks,
    };
  });
  const wins = slots.reduce((n, s) => n + s.wins, 0);
  const cooks = slots.reduce((n, s) => n + s.cooks, 0);
  const lined = slots
    .map((s) => `${s.id} ${s.wins} win${s.wins === 1 ? "" : "s"}`)
    .join(" · ");
  return {
    slots,
    wins,
    cooks,
    detail: cooks
      ? `${wins} product wins across ${cooks} finished cooks · ${lined}`
      : "No campaign finishes in the registry yet",
  };
}

export function getProductStory(): ProductStory {
  const pipeline = PIPELINE_STAGES.map((stage) => {
    const r = collectStageResults(stage, STORY_VARIANT);
    return {
      stage,
      ready: r.artifacts.some((a) => a.exists),
    };
  });
  const finishReady = Boolean(pipeline.find((p) => p.stage === "finish")?.ready);
  const pipelineReady = pipeline.filter((p) => p.ready).length;

  const gates = evaluateSignoffGates(STORY_VARIANT);
  const pillarIds = ["timing", "geometry", "equivalence", "power"];
  const pillars = gates.gates.filter((g) => pillarIds.includes(g.id));
  const signoffPassed = pillars.filter((g) => g.ok).length;
  const leftoverBit = leftoverNamedBit(
    gates.gates.find((g) => g.id === "signoff_all")?.detail ??
      gates.gates.find((g) => g.id === "equivalence")?.detail ??
      "",
  );
  const ecoApply = readReportFile("eco_apply_eco_scratch.json");
  const ecoLeftover =
    typeof ecoApply?.leftover === "string" && ecoApply.leftover
      ? ecoApply.leftover
      : "";
  const ecoCloseLeftover = leftoverSetupOpenDetail(
    readReportFile("signoff_all_eco_scratch.json"),
  );

  const staIrReport = readReport("sta_ir_aware");
  const staBlock = (staIrReport?.sta ?? null) as
    | {
        slack_ns?: number;
        slack_ir_ns?: number;
        n_joined?: number;
        n_gates?: number;
      }
    | null;
  const staIrBlock = (staIrReport?.ir ?? null) as
    | { worst_cell_ir_mv?: number; map?: string }
    | null;
  const staIrReady = staIrReport?.ok === true && staBlock?.slack_ir_ns != null;
  const staMap = String(staIrBlock?.map ?? "");
  const staCurrent =
    staMap.includes("_direct.map.csv") && staIrBlock?.worst_cell_ir_mv != null
      ? ` · current_run ${Number(staIrBlock.worst_cell_ir_mv).toFixed(3)} mV`
      : "";
  const staIr = {
    ready: staIrReady,
    slackNs: num(staBlock?.slack_ns),
    slackIrNs: num(staBlock?.slack_ir_ns),
    nJoined: num(staBlock?.n_joined),
    nGates: num(staBlock?.n_gates),
    detail: staIrReady
      ? `slack ${Number(staBlock?.slack_ns).toFixed(4)} ns → IR ${Number(staBlock?.slack_ir_ns).toFixed(4)} ns · ${staBlock?.n_joined}/${staBlock?.n_gates} gates joined${staCurrent}`
      : "Educational NLDM × ITerm V — run sta_ir_aware after dynamic_ir current_run",
  };

  const gold = readReport("dynamic_ir");
  const goldPresent =
    Boolean(gold?.gold) && Math.abs(Number(gold?.worst_droop_mv) - IR_GOLD_MV) < 0.02;
  const liveMv = readCurrentRunDroopMv(STORY_VARIANT);
  const currentPresent =
    liveMv != null && Math.abs(liveMv - IR_GOLD_MV) > 1.0;

  const product = summarizeProduct(readJsonl("sim/dse/campaign_experiments.jsonl"));
  const progress = readProgress();
  const done = new Set(progress.completed_lessons ?? []);
  const doneLessons = LESSONS.filter((l) => done.has(l.id)).length;
  const nextLesson = LESSONS.find((l) => !done.has(l.id)) ?? null;

  const pathSteps: StoryStep[] = [
    {
      id: "rtl",
      label: "RTL",
      href: "/flow?phase=rtl",
      ready: true,
      detail: "GCD Verilog in FlowLab",
    },
    {
      id: "pipeline",
      label: "RTL → GDS",
      href: "/flow?phase=finish",
      ready: finishReady,
      detail: finishReady
        ? `${pipelineReady}/${pipeline.length} FlowLab phases have artifacts`
        : `${pipelineReady}/${pipeline.length} phases ready — finish not present`,
    },
    {
      id: "signoff",
      label: leftoverBit ? "Signoff · leftover named" : "Signoff",
      href: "/flow?phase=finish&focus=signoff#signoff",
      ready: gates.ok,
      detail:
        pillars.length === 0
          ? "Four pillars: STA · DRC · LVS · power"
          : gates.ok
            ? `${signoffPassed}/${pillars.length} pillars ok${leftoverBit}`
            : `${signoffPassed}/${pillars.length} pillars · signoff_all not close${leftoverBit}`,
    },
    {
      id: "sta-ir",
      label: "STA IR-aware",
      href: "/flow?phase=finish&focus=sta-ir#sta-ir",
      ready: staIr.ready,
      detail: staIr.detail,
    },
    {
      id: "ir",
      label: "Dynamic IR",
      href: "/flow?phase=finish&focus=ir#ir",
      ready: currentPresent || goldPresent,
      detail: currentPresent
        ? `current_run ${liveMv != null ? liveMv.toFixed(3) : "absent"} mV · gold ${IR_GOLD_MV} mV locked (another mesh)`
        : `Gold ${IR_GOLD_MV} mV is the frozen reference_run`,
    },
    {
      id: "eco",
      label: ecoLeftover ? "ECO · leftover named" : "ECO",
      href: "/flow?phase=finish#eco",
      ready: fs.existsSync(path.join(LEARN_ROOT, "sim/reports/eco_flowlab.json")),
      detail: ecoLeftover
        ? ecoCloseLeftover
          ? `Propose on flowlab. Apply leftover: ${ecoLeftover}. Close leftover: ${ecoCloseLeftover}`
          : `Propose on flowlab. Apply leftover: ${ecoLeftover}`
        : "Propose on flowlab. Apply and signoff_all close on eco_scratch only.",
    },
    {
      id: "dse",
      label: "DSE (proposer)",
      href: "/lab",
      ready: product.wins > 0,
      detail: product.detail,
    },
  ];

  const surfaces: ProductStory["surfaces"] = [
    {
      id: "course",
      label: "Course",
      href: "/lessons",
      ready: doneLessons > 0,
      detail: `${doneLessons}/${LESSONS.length} lessons closed`,
    },
    {
      id: "lab",
      label: "Lab",
      href: "/lab",
      ready: goldPresent,
      detail: `Physics ledger · gold ${IR_GOLD_MV} mV · not a product win`,
    },
    {
      id: "product",
      label: "Product",
      href: "/product",
      ready: product.wins > 0,
      detail: `${product.wins} wins · official netlist · fixed die`,
    },
  ];

  return {
    title: "RTL → GDS → signoff",
    lead:
      "Course teaches the flow. Lab measures IR on the same GCD. Product cooks physical knobs on the official netlist. DSE does not run signoff_all. Wins stay in win_rule.py.",
    variant: STORY_VARIANT,
    surfaces,
    path: pathSteps,
    pipeline: {
      ready: pipelineReady,
      total: pipeline.length,
      finishReady,
    },
    signoff: {
      ok: pillars.length ? gates.ok : null,
      passed: signoffPassed,
      total: Math.max(pillars.length, 4),
      detail:
        pillars.length === 0
          ? "Run finish, then the four signoff pillars"
          : gates.ok
            ? `${signoffPassed}/${pillars.length} pillars pass on ${STORY_VARIANT}${leftoverBit}`
            : `${signoffPassed}/${pillars.length} pillars · signoff_all not close${leftoverBit}`,
    },
    ir: {
      goldMv: IR_GOLD_MV,
      currentMv: currentPresent ? liveMv : null,
      goldPresent,
      currentPresent,
      detail: currentPresent
        ? `reference_run ${IR_GOLD_MV} mV · current_run ${Number(liveMv).toFixed(3)} mV · do not mix`
        : `reference_run ${IR_GOLD_MV} mV · current_run absent (dynamic_ir_*_direct.json)`,
    },
    staIr,
    product,
    course: {
      done: doneLessons,
      total: LESSONS.length,
      nextId: nextLesson?.id ?? null,
      nextTitle: nextLesson?.title ?? null,
    },
  };
}

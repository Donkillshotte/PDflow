/**
 * One snapshot for the three surfaces. Every value is read from the current
 * invocation; every value is read from the current reports on disk.
 */
import fs from "fs";
import path from "path";
import { LEARN_ROOT, LESSONS, readProgress } from "./course";
import { collectStageResults } from "./results";
import {
  evaluateSignoffGates,
  leftoverMcmmDetail,
  leftoverMustConnectDetail,
  leftoverSetupOpenDetail,
} from "./signoff";
import {
  irMeshLedgerDetail,
  leftoverNamedBit,
} from "./leftoverCatalog";
import { isCurrentReport } from "./liveReports";
import { PIPELINE_STAGES } from "./jobs";

export const STORY_VARIANT = "flowlab";
export { leftoverNamedBit };

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
  clockNs: number | null;
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
    runMv: number | null;
    present: boolean;
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

function readReport(name: string): Record<string, unknown> | null {
  return readReportFile(`${name}_${STORY_VARIANT}.json`);
}

function readReportFile(fileName: string): Record<string, unknown> | null {
  const p = path.join(LEARN_ROOT, "sim/reports", fileName);
  if (!isCurrentReport(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Live I(t) result from the requested variant. */
export function readLiveRunDroopMv(variant = STORY_VARIANT): number | null {
  const run = readReportFile(`dynamic_ir_${variant}_direct.json`);
  if (!run) return null;
  const top = num(run.worst_droop_mv);
  if (top != null) return top;
  const dyn = run.dynamic as { worst_droop?: number; worst_droop_mv?: number } | undefined;
  if (dyn?.worst_droop_mv != null) return num(dyn.worst_droop_mv);
  return dyn?.worst_droop != null ? Number(dyn.worst_droop) * 1e3 : null;
}

function summarizeProduct(report: Record<string, unknown> | null): ProductStory["product"] {
  const candidates = report && Number.isFinite(Number(report.n_candidates))
    ? Math.max(0, Number(report.n_candidates))
    : 0;
  const variant = String(report?.variant ?? STORY_VARIANT);
  return {
    slots: report
      ? [{ id: `${variant} live`, clockNs: num(report.period_ns), cooks: report.ok === true ? 1 : 0 }]
      : [],
    cooks: report?.ok === true ? 1 : 0,
    detail: report ? `${candidates} candidates from the current invocation` : "No current DSE invocation report",
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
  const timingReport = readReport("sta_signoff");
  const lvsReport = readReport("lvs_signoff");
  const powerReport = readReport("power_signoff");
  const currentLeftovers = [
    leftoverSetupOpenDetail(timingReport),
    leftoverMcmmDetail(timingReport),
    leftoverMustConnectDetail(lvsReport),
    irMeshLedgerDetail(powerReport),
  ]
    .filter((item): item is string => Boolean(item))
    .join(" · ");
 const leftoverBit = leftoverNamedBit(
    currentLeftovers ||
      (gates.gates.find((g) => g.id === "signoff_all")?.detail ??
        gates.gates.find((g) => g.id === "equivalence")?.detail ??
        ""),
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
      ? ` · current_run sta_ir_aware_${STORY_VARIANT}.json ${Number(staIrBlock.worst_cell_ir_mv).toFixed(3)} mV`
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

  const liveMv = readLiveRunDroopMv(STORY_VARIANT);
  const livePresent = liveMv != null;

  const product = summarizeProduct(readReport("dse"));
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
      ready: livePresent,
      detail: livePresent
        ? `live run dynamic_ir_${STORY_VARIANT}_direct.json ${liveMv!.toFixed(3)} mV · same-run mesh fingerprint`
        : "Live Dynamic IR report absent — run the current design",
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
      ready: product.cooks > 0,
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
      ready: livePresent,
      detail: "Physics ledger · current-run measurements · not a product win",
    },
    {
      id: "product",
      label: "Product",
      href: "/product",
      ready: product.cooks > 0,
      detail: product.detail,
    },
  ];

  return {
    title: "RTL → GDS → signoff",
    lead:
      "Course teaches the flow. Lab measures the selected design from the current invocation. Product views expose only current-run artifacts.",
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
      runMv: livePresent ? liveMv : null,
      present: livePresent,
      detail: livePresent
        ? `live run dynamic_ir_${STORY_VARIANT}_direct.json ${Number(liveMv).toFixed(3)} mV · compare only with a matching live mesh`
        : "live run absent (dynamic_ir_*_direct.json)",
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

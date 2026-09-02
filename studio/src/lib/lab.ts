/**
 * Lab bench snapshot: physics ledger + experiment-vs-experiment comparison.
 * Product wins stay in win_rule.py; this file only reads artifacts.
 */
import fs from "fs";
import path from "path";
import { LEARN_ROOT } from "./course";
import { IR_CURRENT_MV, IR_GOLD_MV, productVerdict, type CampRow } from "./story";

const SLOTS: { id: string; clockNs: number }[] = [
  { id: "gcd", clockNs: 0.46 },
  { id: "spi", clockNs: 1.0 },
  { id: "ibex", clockNs: 2.2 },
  { id: "aes", clockNs: 0.82 },
  { id: "dynamic_node", clockNs: 6.0 },
];

function readJson(rel: string): Record<string, unknown> | null {
  const p = path.join(LEARN_ROOT, rel);
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
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

function n(v: unknown): number | null {
  if (v == null || v === "") return null;
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

export type LabCheck = {
  id: string;
  design: string;
  ok: boolean;
  status: string;
  quantity: string;
  value: unknown;
  bound: string;
  note: string;
};

export type AxisDelta = {
  wnsPs: number | null;
  areaPct: number | null;
  powerPct: number | null;
  irPct: number | null;
};

export type ExperimentPair = {
  design: string;
  clockNs: number;
  verdict: string;
  base: { id: string; variant?: string; wnsNs: number | null; irMv: number | null; area: number | null; power: number | null };
  cook: { id: string; variant?: string; wnsNs: number | null; irMv: number | null; area: number | null; power: number | null; note?: string };
  versus: "base" | "previous";
  delta: AxisDelta;
};

function axis(cand: CampRow, base: CampRow): AxisDelta {
  const dw =
    cand.finish_wns_ns != null && base.finish_wns_ns != null
      ? (Number(cand.finish_wns_ns) - Number(base.finish_wns_ns)) * 1000
      : null;
  const pct = (a: number | null | undefined, b: number | null | undefined) => {
    if (a == null || b == null || Math.abs(Number(b)) < 1e-18) return null;
    return ((Number(b) - Number(a)) / Math.abs(Number(b))) * 100;
  };
  return {
    wnsPs: dw,
    areaPct: pct(cand.stdcell_um2, base.stdcell_um2),
    powerPct: pct(cand.power_w, base.power_w),
    irPct: pct(cand.ir_drop_v, base.ir_drop_v),
  };
}

function pairOf(design: string, clockNs: number, cook: CampRow, ref: CampRow, versus: "base" | "previous"): ExperimentPair {
  return {
    design,
    clockNs,
    verdict: productVerdict(cook, ref),
    versus,
    base: {
      id: String(ref.id ?? ref.variant ?? "ref"),
      variant: ref.variant,
      wnsNs: n(ref.finish_wns_ns),
      irMv: ref.ir_drop_v != null ? Number(ref.ir_drop_v) * 1e3 : null,
      area: n(ref.stdcell_um2),
      power: n(ref.power_w),
    },
    cook: {
      id: String(cook.id ?? cook.variant ?? "cook"),
      variant: cook.variant,
      wnsNs: n(cook.finish_wns_ns),
      irMv: cook.ir_drop_v != null ? Number(cook.ir_drop_v) * 1e3 : null,
      area: n(cook.stdcell_um2),
      power: n(cook.power_w),
      note: cook.notes,
    },
    delta: axis(cook, ref),
  };
}

export function campaignComparisons(rows = readJsonl("sim/dse/campaign_experiments.jsonl")): ExperimentPair[] {
  const out: ExperimentPair[] = [];
  for (const slot of SLOTS) {
    const same = rows.filter(
      (r) => r.design === slot.id && Math.abs(Number(r.clock_ns) - slot.clockNs) < 1e-6 && r.status === "done" && r.finish_wns_ns != null,
    );
    const base = same.find((r) => r.role === "base") ?? same[0];
    const cooks = same
      .filter((r) => r !== base && r.role !== "base")
      .sort((a, b) => Number(a.created_at ?? 0) - Number(b.created_at ?? 0));
    if (!base || !cooks.length) continue;
    const latest = cooks[cooks.length - 1]!;
    out.push(pairOf(slot.id, slot.clockNs, latest, base, "base"));
    if (cooks.length >= 2) {
      const prev = cooks[cooks.length - 2]!;
      out.push(pairOf(slot.id, slot.clockNs, latest, prev, "previous"));
    }
  }
  return out;
}

export function getLabSnapshot() {
  const physics = readJson("sim/reports/lab_physics_flowlab.json");
  const pairs = campaignComparisons();
  const latest = pairs.filter((p) => p.versus === "base");
  const dse = readJson("sim/reports/dse_flowlab.json");
  const staIr = readJson("sim/reports/sta_ir_aware_flowlab.json");
  const sta = (staIr?.sta ?? {}) as Record<string, unknown>;
  return {
    title: "Lab bench",
    lead: "Numbers that survive a rail-scale and same-mesh check. Not foundry correlation.",
    goldMv: IR_GOLD_MV,
    currentMv: IR_CURRENT_MV,
    physics: physics
      ? {
          ok: physics.ok === true,
          nReady: Number(physics.n_ready ?? 0),
          nChecks: Number(physics.n_checks ?? 0),
          watch: (physics.watch as string[]) ?? [],
          fail: (physics.fail as string[]) ?? [],
          gap: (physics.gap as string[]) ?? [],
          checks: (physics.checks as LabCheck[]) ?? [],
          slots: physics.slots ?? [],
          note: physics.note,
        }
      : null,
    staIr: {
      slackNs: n(sta.slack_ns),
      slackIrNs: n(sta.slack_ir_ns),
      nJoined: n(sta.n_joined),
      nGates: n(sta.n_gates),
      degradationPs: n(sta.degradation_ps),
    },
    dse: dse
      ? {
          ok: dse.ok === true,
          summary: String(dse.summary ?? ""),
          nCandidates: Number(dse.n_candidates ?? 0),
        }
      : null,
    comparisons: pairs,
    latestBySlot: latest,
  };
}

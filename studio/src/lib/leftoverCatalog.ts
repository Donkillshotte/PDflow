/**
 * Machine-readable leftover catalog. Gated leftovers stay named; they are not
 * closed on Nangate45. See learn/signoff/leftover_catalog.json.
 */
import fs from "fs";
import path from "path";
import { LEARN_ROOT } from "./course";
import {
  leftoverDeckCoverageDetail,
  leftoverMcmmDetail,
  leftoverMustConnectDetail,
  leftoverSetupOpenDetail,
} from "./signoff";

export type LeftoverKind = "gated" | "built" | "locked" | "forbidden_retry";

export type LeftoverCatalogItem = {
  id: string;
  kind: LeftoverKind;
  variant?: string;
  report?: string;
  json_pointer?: string;
  suite_hooks?: string[];
  studio_surfaces?: string[];
  detail_needles?: string[];
};

export type LeftoverCatalog = {
  version: number;
  items: LeftoverCatalogItem[];
  home_compact_phrases?: string[];
};

let cached: LeftoverCatalog | null = null;

export function loadLeftoverCatalog(): LeftoverCatalog {
  if (cached) return cached;
  const p = path.join(LEARN_ROOT, "signoff/leftover_catalog.json");
  cached = JSON.parse(fs.readFileSync(p, "utf8")) as LeftoverCatalog;
  return cached;
}

export function catalogItemsForHook(hookId: string): LeftoverCatalogItem[] {
  return loadLeftoverCatalog().items.filter((item) =>
    (item.suite_hooks ?? []).includes(hookId),
  );
}

export function leftoverIdsMatchingDetail(
  detail: string,
  hookId?: string,
): string[] {
  const items = hookId
    ? catalogItemsForHook(hookId)
    : loadLeftoverCatalog().items;
  return items
    .filter((item) =>
      (item.detail_needles ?? []).some((needle) => detail.includes(needle)),
    )
    .map((item) => item.id);
}

/** Compact leftover list for home / suite. Needles come from the catalog. */
export function leftoverNamedBit(detail: string): string {
  const phrases = loadLeftoverCatalog().home_compact_phrases ?? [
    "leftover must-connect",
    "leftover setup open",
    "leftover no MCMM",
    "leftover no density",
    "IR meshes not comparable",
  ];
  const bits: string[] = [];
  for (const phrase of phrases) {
    if (!detail.includes(phrase)) continue;
    if (phrase === "leftover must-connect") {
      const must = detail.match(/leftover must-connect \d+(?:\s*\([^)]+\))?/);
      if (must) bits.push(must[0]);
    } else if (phrase === "leftover setup open") {
      const setup = detail.match(/leftover setup open \(WNS [^)]+\)/);
      if (setup) bits.push(setup[0]);
    } else if (phrase === "leftover no MCMM") {
      const mcmm = detail.match(/leftover no MCMM \([^)]+\)/);
      if (mcmm) bits.push(mcmm[0]);
    } else if (phrase === "leftover no density") {
      bits.push("leftover no density / named ERC");
    } else if (phrase === "IR meshes not comparable") {
      bits.push("IR meshes not comparable");
    }
  }
  if (!bits.length) {
    const at = detail.indexOf("leftover");
    return at >= 0 ? ` · ${detail.slice(at)}` : "";
  }
  return ` · ${bits.join(" · ")}`;
}

function readSignoffReport(
  name: string,
  variants: string[] = ["flowlab", "learn"],
): Record<string, unknown> | null {
  for (const variant of variants) {
    const p = path.join(LEARN_ROOT, "sim/reports", `${name}_${variant}.json`);
    if (!fs.existsSync(p)) continue;
    try {
      return JSON.parse(fs.readFileSync(p, "utf8")) as Record<string, unknown>;
    } catch {
      /* ignore */
    }
  }
  return null;
}

export function irMeshLedgerDetail(
  report: Record<string, unknown> | null,
): string | null {
  if (!report) return null;
  const ledger = report.ir_mesh_ledger as
    | { comparable?: boolean; n_meshes?: number }
    | undefined;
  if (!ledger || ledger.comparable !== false) return null;
  const n = Number(ledger.n_meshes ?? 0);
  return n > 0 ? `IR meshes not comparable (${n} meshes)` : "IR meshes not comparable";
}

export function leftoverCompactFromReport(
  report: Record<string, unknown> | null,
  opts?: { pillarsOk?: boolean },
): string {
  if (!report) return "";
  const bits: string[] = [];
  if (opts?.pillarsOk !== false && report.ok === true) {
    bits.push("4/4 pillars ok");
  }
  const must = leftoverMustConnectDetail(report);
  if (must) bits.push(must);
  const setup = leftoverSetupOpenDetail(report);
  if (setup) {
    const compact = setup.split(";")[0]?.trim() ?? setup;
    bits.push(compact);
  }
  const mcmm = leftoverMcmmDetail(report);
  if (mcmm) bits.push(mcmm);
  const deck = leftoverDeckCoverageDetail(report);
  if (deck?.includes("leftover no")) bits.push("leftover no density / named ERC");
  const mesh = irMeshLedgerDetail(report);
  if (mesh) bits.push(mesh);
  return bits.join(" · ");
}

export function staSignoffHookDetail(): string {
  for (const variant of ["flowlab", "learn"]) {
    const sta = readSignoffReport("sta_signoff", [variant]);
    const all = readSignoffReport("signoff_all", [variant]);
    const report = (sta ?? all) as Record<string, unknown> | null;
    if (!report) continue;
    const bits = ["educational golden ≥ −0.04"];
    const setup = leftoverSetupOpenDetail(sta ?? all);
    if (setup) bits.push(setup);
    const mcmm = leftoverMcmmDetail(sta ?? all);
    if (mcmm) bits.push(mcmm);
    if (bits.length > 1) return bits.join(" · ");
    if (typeof report.summary === "string") return report.summary;
  }
  return "WNS/TNS vs golden-gcd · run_sta_signoff.sh";
}

export function drcSignoffHookDetail(): string {
  for (const variant of ["flowlab", "learn"]) {
    const drc = readSignoffReport("drc_signoff", [variant]);
    if (drc && typeof drc.summary === "string") {
      const summary = String(drc.summary);
      if (summary.includes("leftover no density") || summary.includes("antenna")) {
        return summary;
      }
    }
    const all = readSignoffReport("signoff_all", [variant]);
    const deck = leftoverDeckCoverageDetail(all ?? drc);
    if (deck) return `Route DRC + KLayout GDS · ${deck}`;
  }
  return "Route DRC + KLayout GDS · run_drc_signoff.sh";
}

export function klayoutDrcHookDetail(): string {
  const deckPath = path.join(LEARN_ROOT, "sim/reports/drc_deck_coverage.json");
  let deckReport: Record<string, unknown> | null = null;
  if (fs.existsSync(deckPath)) {
    try {
      deckReport = JSON.parse(
        fs.readFileSync(deckPath, "utf8"),
      ) as Record<string, unknown>;
    } catch {
      /* ignore */
    }
  }
  const all = readSignoffReport("signoff_all");
  const deck =
    leftoverDeckCoverageDetail(deckReport) ??
    leftoverDeckCoverageDetail(all);
  if (deck) return `${deck} · run_klayout_drc.sh`;
  return "run_klayout_drc.sh";
}

export function powerSignoffHookDetail(): string {
  for (const variant of ["flowlab", "learn"]) {
    const pwr = readSignoffReport("power_signoff", [variant]);
    const all = readSignoffReport("signoff_all", [variant]);
    if (!pwr && !all) continue;
    let summary =
      typeof pwr?.summary === "string" ? String(pwr.summary) : "chip IR · golden gate";
    summary = summary.replace(/^Chip IR/, "chip IR");
    const mesh = irMeshLedgerDetail(all ?? pwr);
    if (mesh && !summary.includes("IR meshes not comparable")) {
      return `${summary} · ${mesh}`;
    }
    return summary;
  }
  return "chip IR · golden gate";
}

export function signoffAllHookDetail(): string {
  for (const variant of ["flowlab", "learn"]) {
    const all = readSignoffReport("signoff_all", [variant]);
    if (!all) continue;
    const compact = leftoverCompactFromReport(all, { pillarsOk: true });
    if (compact) return compact;
    if (typeof all.summary === "string") return String(all.summary);
  }
  return "run_signoff_all.sh";
}

export function lvsSignoffHookDetail(): string {
  for (const variant of ["flowlab", "learn"]) {
    const lvs = readSignoffReport("lvs_signoff", [variant]);
    const all = readSignoffReport("signoff_all", [variant]);
    const report = (lvs ?? all) as Record<string, unknown> | null;
    if (!report) continue;
    const must =
      leftoverMustConnectDetail(report) ??
      leftoverMustConnectDetail(all);
    const bits = ["KLayout GDS vs filtered CDL"];
    if (must) bits.push(must);
    bits.push("VIA_* flatten leftover");
    return bits.join(" · ");
  }
  return "KLayout GDS vs filtered CDL · leftover must-connect 2 (DFF_X2) · VIA_* flatten leftover";
}

export function hookLeftoverIds(hookId: string, detail: string): string[] {
  return leftoverIdsMatchingDetail(detail, hookId);
}

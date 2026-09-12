import fs from "fs";
import path from "path";
import { LEARN_ROOT, REPO_ROOT } from "./course";
import { resultsDir } from "./open";
import { normalizeResultsVariant } from "./pathGuard";
import { candidateOrfsRoot } from "./candidateWorkspace";
import {
  PHASE_COMPARE,
  PHASE_GALLERY,
  PHASE_LAYERS,
  type LayoutPhaseId,
} from "./layoutStudio";

export type { LayoutPhaseId } from "./layoutStudio";

export type LayoutPreviewConfig = {
  phaseId: LayoutPhaseId;
  /** Stage passed to /api/inspect and web viewer when no override */
  inspectStage: string;
  /** Primary ODB for viewer / headless capture */
  odb: string | null;
  /** ORFS save_images PNG under flow/reports/.../{variant}/ */
  orfsReportPng: string | null;
  /** Curated gui-shots under learn/reference/gui-shots/ */
  guiShot: string | null;
  label: string;
  layerHint?: string;
};

const FLOW = () => path.join(REPO_ROOT, "tools/OpenROAD-flow-scripts/flow");

export const PHASE_LAYOUT: Record<LayoutPhaseId, LayoutPreviewConfig> = {
  rtl: {
    phaseId: "rtl",
    inspectStage: "synth",
    odb: null,
    orfsReportPng: null,
    guiShot: null,
    label: "RTL · sim + VCD",
  },
  synth: {
    phaseId: "synth",
    inspectStage: "synth",
    odb: "1_synth.odb",
    orfsReportPng: null,
    guiShot: null,
    label: "Synthesis · gate-level ODB",
  },
  floorplan: {
    phaseId: "floorplan",
    inspectStage: "floorplan",
    odb: "2_4_floorplan_pdn.odb",
    orfsReportPng: null,
    guiShot: "03_pdn.png",
    label: "Floorplan · die + PDN straps",
    layerHint: "Rows + VDD/VSS — cells arrive at place",
  },
  pdn: {
    phaseId: "pdn",
    inspectStage: "pdn",
    odb: "2_4_floorplan_pdn.odb",
    orfsReportPng: null,
    guiShot: "03_pdn_labeled.png",
    label: "PDN · VDD/VSS straps",
    layerHint: "Metal4/7 straps · M1 rails",
  },
  place: {
    phaseId: "place",
    inspectStage: "place",
    odb: "3_5_place_dp.odb",
    orfsReportPng: "final_placement.webp.png",
    guiShot: "05_place_dp.png",
    label: "Placement · standard cells",
    layerHint: "Cells legalized on rows",
  },
  cts: {
    phaseId: "cts",
    inspectStage: "cts",
    odb: "4_cts.odb",
    orfsReportPng: "cts_core_clock.webp.png",
    guiShot: "06_cts.png",
    label: "Clock tree · buffers + skew",
  },
  route: {
    phaseId: "route",
    inspectStage: "route",
    odb: "5_2_route.odb",
    orfsReportPng: "final_routing.webp.png",
    guiShot: "08_route_labeled.png",
    label: "Detailed route · metal layers",
    layerHint: "Red ≈ M2 · green ≈ M3",
  },
  finish: {
    phaseId: "finish",
    inspectStage: "finish",
    odb: "6_final.odb",
    orfsReportPng: "final_all.webp.png",
    guiShot: "09_final.png",
    label: "Finish · GDS signoff view",
  },
  pkg: {
    phaseId: "pkg",
    inspectStage: "finish",
    odb: "6_final.odb",
    orfsReportPng: "final_ir_drop.webp.png",
    guiShot: "orfs_final_ir_drop.png",
    label: "PKG · finish layout / system PDN",
    layerHint: "Current finish ODB · package metrics below",
  },
};

export const PHYSICAL_LAYOUT_PHASES = new Set<LayoutPhaseId>([
  "synth",
  "floorplan",
  "pdn",
  "place",
  "cts",
  "route",
  "finish",
  "pkg",
]);

function resultsRoot(variant: string, runId?: string | null) {
  const v = normalizeResultsVariant(variant);
  if (runId) {
    if (v !== "flowlab") throw new Error("REFUSED: candidates use the FlowLab variant");
    return path.join(candidateOrfsRoot(runId), "results/nangate45/gcd/flowlab");
  }
  return resultsDir(v);
}

function reportsDir(variant: string, runId?: string | null) {
  const v = normalizeResultsVariant(variant);
  if (runId) {
    if (v !== "flowlab") throw new Error("REFUSED: candidates use the FlowLab variant");
    return path.join(candidateOrfsRoot(runId), "reports/nangate45/gcd/flowlab");
  }
  return path.join(
    FLOW(),
    v.startsWith("lab_asap7_") ? "reports/asap7/gcd" : "reports/nangate45/gcd",
    v,
  );
}

const GUI_SHOTS_DIR = () =>
  path.resolve(path.join(LEARN_ROOT, "reference/gui-shots"));

const SHOT_NAME_RE = /^[A-Za-z0-9._-]+\.(png|webp|jpe?g)$/;

export function resolveNamedGuiShot(file: string): string | null {
  if (!SHOT_NAME_RE.test(file)) return null;
  const dir = GUI_SHOTS_DIR();
  const abs = path.resolve(dir, file);
  if (abs !== path.join(dir, file) && !abs.startsWith(dir + path.sep)) {
    return null;
  }
  if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) return null;
  return abs;
}

function guiShotAbs(name: string) {
  return resolveNamedGuiShot(name) ?? path.join(GUI_SHOTS_DIR(), name);
}

function shotUrl(file: string) {
  return `/api/layout-preview/image?shot=${encodeURIComponent(file)}`;
}

function cacheAbs(variant: string, phaseId: LayoutPhaseId, runId?: string | null) {
  const root = runId
    ? path.join(candidateOrfsRoot(runId), "previews")
    : path.join(LEARN_ROOT, "sim/previews");
  return path.join(
    root,
    normalizeResultsVariant(variant),
    `${phaseId}.png`,
  );
}

export function resolveLayoutImageAbs(
  phaseId: LayoutPhaseId,
  variant: string,
  runId?: string | null,
): { abs: string; source: "cache" | "orfs" | "gui_shot" | "odb" } | null {
  variant = normalizeResultsVariant(variant);
  const cfg = PHASE_LAYOUT[phaseId];
  // A live ODB is authoritative. Never mask a saved native-tool edit with a
  // pedagogical screenshot or an image generated from an older database.
  // Synthesis ODBs intentionally have no die geometry; do not launch a native
  // capture process for a 0×0 database just to produce a misleading image.
  if (phaseId === "synth") return null;
  if (cfg.odb) {
    const odbAbs = path.join(resultsRoot(variant, runId), cfg.odb);
    if (fs.existsSync(odbAbs)) {
      const cached = cacheAbs(variant, phaseId, runId);
      const odbMtime = fs.statSync(odbAbs).mtimeMs;
      if (fs.existsSync(cached) && fs.statSync(cached).mtimeMs >= odbMtime) {
        // The bytes are cached, but their authority is still the current ODB.
        // Expose provenance rather than making the UI look like it selected a
        // static screenshot.
        return { abs: cached, source: "odb" };
      }
      // Package/System PDN is a read-only analysis surface, but it still
      // needs a useful design canvas before its optional package-specific
      // preview has been generated. Reuse the current finish preview only
      // when it was generated from an ODB at least as new as this input;
      // never fall back to a stale or pedagogical image.
      if (phaseId === "pkg") {
        const finishCached = cacheAbs(variant, "finish", runId);
        if (
          fs.existsSync(finishCached) &&
          fs.statSync(finishCached).mtimeMs >= odbMtime
        ) {
          return { abs: finishCached, source: "odb" };
        }
      }
      // Preview generation is an agent-owned job. Never spawn OpenROAD from a
      // Next request: a page refresh must not create an unbounded native
      // process outside the resource executor. The UI receives an explicit
      // missing/stale state and POSTs a typed `layout_preview` job instead.
      return null;
    }
  }
  if (cfg.orfsReportPng) {
    const orfs = path.join(reportsDir(variant, runId), cfg.orfsReportPng);
    if (fs.existsSync(orfs)) {
      return { abs: orfs, source: "orfs" };
    }
  }
  const cached = cacheAbs(variant, phaseId, runId);
  if (fs.existsSync(cached)) {
    return { abs: cached, source: "cache" };
  }
  // Static shots are documentation fallback only, when no live ODB exists.
  if (cfg.guiShot) {
    const shot = guiShotAbs(cfg.guiShot);
    if (fs.existsSync(shot)) {
      return { abs: shot, source: "gui_shot" };
    }
  }
  return null;
}

export function layoutPreviewMeta(
  phaseId: LayoutPhaseId,
  variant: string,
  runId?: string | null,
) {
  variant = normalizeResultsVariant(variant);
  const cfg = PHASE_LAYOUT[phaseId];
  const odbAbs = cfg.odb
    ? path.join(resultsRoot(variant, runId), cfg.odb)
    : null;
  const odbExists = Boolean(odbAbs && fs.existsSync(odbAbs));
  const odbStat = odbExists ? fs.statSync(odbAbs!) : null;
  const image = resolveLayoutImageAbs(phaseId, variant, runId);

  // Static gallery/compare shots are useful before a phase has run, but must
  // not compete with the live database once the native tool has produced it.
  // A candidate is an isolated workspace: showing finish screenshots while
  // its checkpoint is absent would falsely imply that the candidate geometry
  // exists. Keep the candidate view explicitly empty until it writes an ODB.
  const gallery = (odbExists || runId ? [] : PHASE_GALLERY[phaseId] ?? [])
    .filter((s) => resolveNamedGuiShot(s.file))
    .map((s) => ({ ...s, url: shotUrl(s.file) }));

  const compare = (odbExists || runId ? [] : PHASE_COMPARE[phaseId] ?? [])
    .filter(
      (p) => resolveNamedGuiShot(p.left.file) && resolveNamedGuiShot(p.right.file),
    )
    .map((p) => ({
      ...p,
      left: { ...p.left, url: shotUrl(p.left.file) },
      right: { ...p.right, url: shotUrl(p.right.file) },
    }));

  const layers = (PHASE_LAYERS[phaseId] ?? []).map((layer) => ({
    ...layer,
    soloAvailable: Boolean(layer.soloShot && resolveNamedGuiShot(layer.soloShot)),
  }));

  return {
    phaseId,
    variant,
    runId: runId ?? null,
    label: cfg.label,
    layerHint: cfg.layerHint,
    inspectStage: cfg.inspectStage,
    odb: cfg.odb,
    odbExists,
    artifact: cfg.odb
      ? {
          path: cfg.odb,
          relativePath: odbAbs
            ? path.relative(REPO_ROOT, odbAbs).replace(/\\/g, "/")
            : null,
          exists: odbExists,
          bytes: odbStat?.size ?? 0,
          modifiedAt: odbStat?.mtime.toISOString() ?? null,
          revision: odbStat ? `${Math.trunc(odbStat.mtimeMs)}:${odbStat.size}` : null,
          runId: runId ?? null,
          authority: runId ? "candidate" : "finish",
          mutable: Boolean(runId),
        }
      : null,
    primaryShot: odbExists ? null : cfg.guiShot,
    image: image
      ? {
          source: image.source,
          rel: path.relative(REPO_ROOT, image.abs).replace(/\\/g, "/"),
        }
      : null,
    physical: PHYSICAL_LAYOUT_PHASES.has(phaseId),
    gallery,
    compare,
    layers,
  };
}

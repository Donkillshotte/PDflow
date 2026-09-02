import fs from "fs";
import path from "path";
import { spawnSync } from "child_process";
import { LEARN_ROOT, REPO_ROOT } from "./course";
import { resultsDir } from "./open";
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
    label: "PKG · IR drop / system PDN",
    layerHint: "Heatmap IR post-finish",
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

function reportsDir(variant: string) {
  return path.join(FLOW(), "reports/nangate45/gcd", variant);
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

function cacheAbs(variant: string, phaseId: LayoutPhaseId) {
  return path.join(LEARN_ROOT, "sim/previews", variant, `${phaseId}.png`);
}

export function resolveLayoutImageAbs(
  phaseId: LayoutPhaseId,
  variant: string,
): { abs: string; source: "cache" | "orfs" | "gui_shot" | "odb" } | null {
  const cfg = PHASE_LAYOUT[phaseId];
  // Pedagogical shots first: route must show metal spaghetti, not a blank iframe.
  if (cfg.guiShot) {
    const shot = guiShotAbs(cfg.guiShot);
    if (fs.existsSync(shot)) {
      return { abs: shot, source: "gui_shot" };
    }
  }
  if (cfg.orfsReportPng) {
    const orfs = path.join(reportsDir(variant), cfg.orfsReportPng);
    if (fs.existsSync(orfs)) {
      return { abs: orfs, source: "orfs" };
    }
  }
  const cached = cacheAbs(variant, phaseId);
  if (fs.existsSync(cached)) {
    return { abs: cached, source: "cache" };
  }
  // Synth ODB has die 0×0 — inst-map looks like overlapping squares. Skip.
  if (phaseId === "synth") return null;
  if (cfg.odb) {
    const odbAbs = path.join(resultsDir(variant), cfg.odb);
    if (fs.existsSync(odbAbs)) {
      const generated = generateLayoutFromOdb(phaseId, variant, cfg.odb);
      if (generated && fs.existsSync(generated)) {
        return { abs: generated, source: "odb" };
      }
    }
  }
  return null;
}

function generateInstMapSvg(
  phaseId: LayoutPhaseId,
  variant: string,
  odbRel: string,
): string | null {
  const odbAbs = path.join(resultsDir(variant), odbRel);
  if (!fs.existsSync(odbAbs)) return null;
  const outDir = path.join(LEARN_ROOT, "sim/previews", variant);
  const outAbs = path.join(outDir, `${phaseId}_instmap.svg`);
  fs.mkdirSync(outDir, { recursive: true });

  const py = `
import odb
db = odb.dbDatabase.create()
odb.read_db(db, ${JSON.stringify(odbAbs)})
block = db.getChip().getBlock()
insts = block.getInsts()
rects = []
xs, ys = [], []
for inst in insts:
    bbox = inst.getBBox()
    if bbox is None:
        continue
    x1, y1, x2, y2 = bbox.xMin(), bbox.yMin(), bbox.xMax(), bbox.yMax()
    xs.extend([x1, x2]); ys.extend([y1, y2])
    rects.append((x1, y1, x2 - x1, y2 - y1))
if not rects:
    raise SystemExit(1)
min_x, max_x = min(xs), max(xs)
min_y, max_y = min(ys), max(ys)
pad = max(max_x - min_x, max_y - min_y) * 0.04 or 1000
min_x -= pad; min_y -= pad; max_x += pad; max_y += pad
w, h = max_x - min_x, max_y - min_y
vw = 800
vh = max(400, int(800 * h / w)) if w else 600
def sx(x): return (x - min_x) / w * vw if w else 0
def sy(y): return vh - (y - min_y) / h * vh if h else 0
lines = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">' % (vw, vh), '<rect width="%d" height="%d" fill="#0a0e14"/>' % (vw, vh)]
for x, y, rw, rh in rects:
    px, py = sx(x), sy(y + rh)
    pw, ph = sx(x + rw) - sx(x), sy(y) - sy(y + rh)
    if pw < 0.3 or ph < 0.3:
        continue
    lines.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="rgba(88,166,255,0.55)" stroke="rgba(88,166,255,0.25)" stroke-width="0.3"/>' % (px, py, pw, ph))
lines.append('<text x="%.0f" y="%.0f" text-anchor="middle" fill="#8b949e" font-size="11">%d instances</text>' % (vw / 2, vh - 8, len(rects)))
lines.append('</svg>')
open(${JSON.stringify(outAbs)}, "w").write(chr(10).join(lines) + chr(10))
print("WROTE", ${JSON.stringify(outAbs)})
`;
  const r = spawnSync("openroad", ["-python", "-no_init", "-exit"], {
    input: py,
    encoding: "utf8",
    timeout: 90_000,
  });
  if (fs.existsSync(outAbs)) return outAbs;
  return null;
}

export function generateLayoutFromOdb(
  phaseId: LayoutPhaseId,
  variant: string,
  odbRel: string,
): string | null {
  const odbAbs = path.join(resultsDir(variant), odbRel);
  if (!fs.existsSync(odbAbs)) return null;

  const outDir = path.join(LEARN_ROOT, "sim/previews", variant);
  const outAbs = path.join(outDir, `${phaseId}.png`);
  fs.mkdirSync(outDir, { recursive: true });

  const tcl = path.join(LEARN_ROOT, "scripts/capture_gui_shots.tcl");
  const r = spawnSync(
    "openroad",
    ["-no_init", "-no_splash", "-exit", tcl],
    {
      env: {
        ...process.env,
        ODB_FILE: odbAbs,
        SHOT_DIR: outDir,
        SHOT_STEM: phaseId,
        DISPLAY: process.env.DISPLAY || ":1",
      },
      encoding: "utf8",
      timeout: 120_000,
      maxBuffer: 4 * 1024 * 1024,
    },
  );
  const out = `${r.stdout || ""}\n${r.stderr || ""}`;
  if (fs.existsSync(outAbs)) return outAbs;
  if (out.includes("WROTE")) {
    const m = out.match(/WROTE\s+(\S+)/);
    if (m && fs.existsSync(m[1]!)) return m[1]!;
  }
  return null;
}

export function layoutPreviewMeta(phaseId: LayoutPhaseId, variant: string) {
  const cfg = PHASE_LAYOUT[phaseId];
  const odbAbs = cfg.odb ? path.join(resultsDir(variant), cfg.odb) : null;
  const image = resolveLayoutImageAbs(phaseId, variant);

  const gallery = (PHASE_GALLERY[phaseId] ?? [])
    .filter((s) => resolveNamedGuiShot(s.file))
    .map((s) => ({ ...s, url: shotUrl(s.file) }));

  const compare = (PHASE_COMPARE[phaseId] ?? [])
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
    label: cfg.label,
    layerHint: cfg.layerHint,
    inspectStage: cfg.inspectStage,
    odb: cfg.odb,
    odbExists: Boolean(odbAbs && fs.existsSync(odbAbs)),
    primaryShot: cfg.guiShot,
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

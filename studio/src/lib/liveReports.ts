import fs from "fs";
import path from "path";
import { resultsDir } from "./open";
import { normalizeResultsVariant } from "./pathGuard";

/** Reports whose values are derived from the finished physical design. */
const DESIGN_REPORT_RE = /^(?:sta_signoff|drc_signoff|lvs_signoff|lvs_deep|power_signoff|signoff_all|dynamic_ir|vectorless|pdn_chip_ir|sta_ir_aware|system_pdn|pkg_signoff|pkg_manifest|signoff_phase2|thermal_signoff|pkg_bump|pkg_rdl|dse|eco)_(flowlab|learn|eco_scratch)(?:_direct)?\.json$/;
const LAB_REPORT_RE = /^(?:lab_asap7(?:\.json|_(?:pkg|pkg_bump|pkg_rdl|system_pdn|thermal|chip_pdn)\.json)|lab_asap7_bspdn_proxy(?:_[a-z0-9][a-z0-9_.+-]*)?\.json|pkg_manifest_lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]\.json)$/;
const LAB_VARIANT_RE = /^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$/;

/** Resolve the variant carried by a derived report, including shared ASAP7 filenames. */
function reportVariant(absPath: string): string | null | undefined {
  const basename = path.basename(absPath);
  const course = basename.match(DESIGN_REPORT_RE);
  if (course) return course[1];
  const manifestName = basename.match(
    /^pkg_manifest_(lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9])\.json$/,
  );
  if (manifestName) {
    try {
      const payload = JSON.parse(fs.readFileSync(absPath, "utf8")) as {
        variant?: unknown;
      };
      return typeof payload.variant === "string" && LAB_VARIANT_RE.test(payload.variant)
        ? payload.variant
        : null;
    } catch {
      return null;
    }
  }
  if (!LAB_REPORT_RE.test(basename)) return undefined;
  try {
    const payload = JSON.parse(fs.readFileSync(absPath, "utf8")) as {
      variant?: unknown;
    };
    return typeof payload.variant === "string" && LAB_VARIANT_RE.test(payload.variant)
      ? payload.variant
      : null;
  } catch {
    return null;
  }
}

/**
 * Return the newest physical artifact used by signoff for a variant.
 * A report older than this point belongs to an earlier invocation and must
 * not be shown as current evidence.
 */
export function currentDesignMtime(variant: string): number | null {
  const normalized = normalizeResultsVariant(variant);
  const dir = resultsDir(normalized);
  const names = ["6_final.odb", "6_final.v", "6_final.spef", "6_final.gds"];
  const mtimes = names
    .map((name) => {
      const p = path.join(/*turbopackIgnore: true*/ dir, name);
      try {
        return fs.statSync(/*turbopackIgnore: true*/ p).mtimeMs;
      } catch {
        return null;
      }
    })
    .filter((mtime): mtime is number => mtime != null);
  return mtimes.length ? Math.max(...mtimes) : null;
}

/** True only when a physical-design report post-dates the current artifacts. */
export function isCurrentReport(absPath: string, expectedVariant?: string): boolean {
  if (!fs.existsSync(absPath)) return false;
  const variant = reportVariant(absPath);
  if (variant === undefined) return true;
  if (variant === null) return false;
  if (expectedVariant && variant !== expectedVariant) return false;
  const current = currentDesignMtime(variant);
  if (current == null) return false;
  try {
    return fs.statSync(absPath).mtimeMs >= current;
  } catch {
    return false;
  }
}

/** True when any derived report/log artifact belongs to the current finish. */
export function isCurrentRunArtifact(absPath: string, variant: string): boolean {
  if (!fs.existsSync(absPath)) return false;
  const current = currentDesignMtime(variant);
  if (current == null) return true;
  try {
    return fs.statSync(absPath).mtimeMs >= current;
  } catch {
    return false;
  }
}

/**
 * Validate an ASAP7 report against the finish variant recorded by the report.
 * Reports are shared filenames in the lab surface, so the payload identity is
 * required before mtime can be used as a freshness signal.
 */
export function isCurrentAsap7Artifact(absPath: string): boolean {
  if (!fs.existsSync(absPath)) return false;
  let variant: string | null = null;
  try {
    const value = JSON.parse(fs.readFileSync(absPath, "utf8")) as {
      variant?: unknown;
      cooks?: Array<{ variant?: unknown }>;
    };
    if (typeof value.variant === "string") variant = value.variant;
    if (!variant && Array.isArray(value.cooks)) {
      const variants = value.cooks
        .map((row) => (typeof row?.variant === "string" ? row.variant : null))
        .filter((item): item is string => item != null);
      variant = variants.at(-1) ?? null;
    }
  } catch {
    return false;
  }
  if (variant && !/^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$/.test(variant)) {
    return false;
  }
  const current = variant ? currentDesignMtime(variant) : newestAsap7DesignMtime();
  if (current == null) return false;
  try {
    return fs.statSync(absPath).mtimeMs >= current;
  } catch {
    return false;
  }
}

function newestAsap7DesignMtime(): number | null {
  const root = path.join(
    /*turbopackIgnore: true*/ process.cwd(),
    "../tools/OpenROAD-flow-scripts/flow/results/asap7",
  );
  let newest: number | null = null;
  try {
    for (const design of fs.readdirSync(root, { withFileTypes: true })) {
      if (!design.isDirectory()) continue;
      const designRoot = path.join(root, design.name);
      for (const variant of fs.readdirSync(designRoot, { withFileTypes: true })) {
        if (!variant.isDirectory()) continue;
        const mtime = currentDesignMtime(`lab_asap7_${variant.name.replace(/^lab_asap7_/, "")}`);
        if (mtime != null) newest = newest == null ? mtime : Math.max(newest, mtime);
      }
    }
  } catch {
    return newest;
  }
  return newest;
}

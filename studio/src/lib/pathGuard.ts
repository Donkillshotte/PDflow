import path from "path";

const LAB_VARIANT_RE = /^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$/;
const COURSE_VARIANTS = new Set(["learn", "flowlab", "eco_scratch"]);

export const RESULTS_VARIANTS = COURSE_VARIANTS;

export function normalizeResultsVariant(variant: string): string {
  const v = variant.trim();
  if (!v) {
    throw new Error("REFUSED: empty variant");
  }
  if (v.includes("..") || v.includes("/") || v.includes("\\") || v.includes(":")) {
    throw new Error(`REFUSED: illegal path token in variant (${variant})`);
  }
  if (COURSE_VARIANTS.has(v)) {
    return v;
  }
  if (v.startsWith("lab_asap7_")) {
    if (!LAB_VARIANT_RE.test(v)) {
      throw new Error(`REFUSED: variant charset (${variant})`);
    }
    return v;
  }
  throw new Error(`REFUSED: unknown variant (${variant})`);
}

export function assertUnder(baseDir: string, targetDir: string): string {
  const base = path.resolve(baseDir);
  const resolved = path.resolve(targetDir);
  if (resolved !== base && !resolved.startsWith(base + path.sep)) {
    throw new Error(`REFUSED: path escapes ${baseDir}`);
  }
  return resolved;
}

/**
 * Artifacts exposed by Studio are always single path components. Keeping this
 * stricter than a generic relative-path check prevents callers from turning a
 * safe results directory into an arbitrary file reader or tool input.
 */
export function normalizeRelativeArtifact(artifact: string): string {
  const value = artifact.trim();
  if (!value || value.length > 256 || value.includes("\0")) {
    throw new Error("REFUSED: invalid artifact");
  }
  if (
    path.isAbsolute(value) ||
    value === "." ||
    value === ".." ||
    value.includes("..") ||
    value.includes("/") ||
    value.includes("\\")
  ) {
    throw new Error(`REFUSED: artifact path (${artifact})`);
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._+-]*$/.test(value)) {
    throw new Error(`REFUSED: artifact charset (${artifact})`);
  }
  return value;
}

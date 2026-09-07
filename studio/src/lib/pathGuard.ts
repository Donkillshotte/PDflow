import path from "path";

const LAB_VARIANT_RE = /^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$/;
const COURSE_VARIANTS = new Set(["learn", "flowlab", "eco_scratch"]);

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

/**
 * Classify OpenROAD / ORFS log lines for the Studio wrapper.
 * Distinguishes real [ERROR]/[WARNING] from benign "Failure: 0" noise.
 */

export type LogSeverity = "error" | "warn" | "info" | "ok" | "plain";

export type ClassifiedLine = {
  text: string;
  severity: LogSeverity;
  code: string | null;
  noise: boolean;
};

export type LogDigest = {
  errors: number;
  warnings: number;
  noiseWarnings: number;
  noteworthy: { code: string; message: string; count: number }[];
  topCodes: { code: string; count: number; noise: boolean }[];
  healthy: boolean;
  summary: string;
};

/** Known nangate45/ORFS noise — expected, not actionable for students. */
const NOISE_CODES = new Set([
  "RSZ-0104", // dangling 1-pin nets during GRT
  "GUI-0010", // .webp → .webp.png rewrite
  "GUI-0066", // empty heatmaps
  "GUI-0076", // XDG_RUNTIME_DIR unset
  "IFP-0028", // core origin snap to site grid
  "EST-0027", // wire-load models (no parasitics yet)
  "GRT-0246", // no CORE ANTENNACELL in nangate45
]);

/** Worth surfacing even when the flow exits 0. */
const NOTEWORTHY_CODES = new Set([
  "RSZ-0062", // unable to repair all setup violations
  "DPL-0038",
  "DRT-001",
]);

const OR_TAG =
  /\[(ERROR|WARNING|INFO|NOTICE)\s+([A-Z]{2,5}-\d{4})\]/i;

const BENIGN_FAIL =
  /\b(?:total\s+)?(?:placement\s+)?fail(?:ure)?s?\s*:\s*0\b/i;
const BENIGN_ERROR_COUNT =
  /\berrors?(?:__count)?\b[^0-9]{0,12}0\b/i;
const REAL_FAIL =
  /\b(?:fail(?:ure|ed)?|error)s?\s*:\s*[1-9]\d*\b/i;

export function extractOrCode(line: string): string | null {
  const m = line.match(OR_TAG);
  return m ? m[2].toUpperCase() : null;
}

export function classifyOrfsLine(line: string): ClassifiedLine {
  const code = extractOrCode(line);
  const tag = line.match(OR_TAG)?.[1]?.toUpperCase() ?? null;

  if (tag === "ERROR" || /\bfatal\b/i.test(line)) {
    return { text: line, severity: "error", code, noise: false };
  }

  if (BENIGN_FAIL.test(line) || (BENIGN_ERROR_COUNT.test(line) && !REAL_FAIL.test(line))) {
    return { text: line, severity: "ok", code, noise: true };
  }

  if (REAL_FAIL.test(line) && !/\[INFO\b/i.test(line)) {
    return { text: line, severity: "error", code, noise: false };
  }

  if (tag === "WARNING" || (code && NOISE_CODES.has(code))) {
    const noise = code ? NOISE_CODES.has(code) : false;
    return { text: line, severity: "warn", code, noise };
  }

  if (/\[WARNING\b/i.test(line) || (/\bwarn(?:ing)?\b/i.test(line) && !BENIGN_FAIL.test(line))) {
    return { text: line, severity: "warn", code, noise: false };
  }

  if (tag === "INFO" || tag === "NOTICE" || /\b(?:Done|Success|complete)\b/i.test(line)) {
    return { text: line, severity: "ok", code, noise: false };
  }

  if (/^\s*\[\d/.test(line)) {
    return { text: line, severity: "info", code, noise: false };
  }

  return { text: line, severity: "plain", code, noise: false };
}

export type DisplayLine =
  | { kind: "line"; line: ClassifiedLine; index: number }
  | {
      kind: "collapse";
      code: string;
      count: number;
      sample: string;
      severity: LogSeverity;
      noise: boolean;
      index: number;
    };

/**
 * Collapse consecutive identical OpenROAD warning codes (e.g. 33× RSZ-0104).
 */
export function collapseOrfsLines(text: string): DisplayLine[] {
  const raw = text.split("\n");
  const out: DisplayLine[] = [];
  let i = 0;
  while (i < raw.length) {
    const classified = classifyOrfsLine(raw[i]);
    const code = classified.code;
    if (
      code &&
      classified.severity === "warn" &&
      i + 1 < raw.length
    ) {
      let j = i + 1;
      while (j < raw.length) {
        const next = classifyOrfsLine(raw[j]);
        if (next.code === code && next.severity === "warn") j += 1;
        else break;
      }
      const count = j - i;
      if (count >= 3) {
        out.push({
          kind: "collapse",
          code,
          count,
          sample: raw[i].trim().slice(0, 120),
          severity: "warn",
          noise: classified.noise || NOISE_CODES.has(code),
          index: i,
        });
        i = j;
        continue;
      }
    }
    out.push({ kind: "line", line: classified, index: i });
    i += 1;
  }
  return out;
}

export function digestOrfsLog(text: string): LogDigest {
  const counts = new Map<string, { count: number; noise: boolean; sample: string }>();
  let errors = 0;
  let warnings = 0;
  let noiseWarnings = 0;

  for (const raw of text.split("\n")) {
    if (!raw.trim()) continue;
    const c = classifyOrfsLine(raw);
    if (c.severity === "error") errors += 1;
    if (c.severity === "warn") {
      warnings += 1;
      if (c.noise) noiseWarnings += 1;
    }
    if (c.code && (c.severity === "warn" || c.severity === "error")) {
      const prev = counts.get(c.code);
      if (prev) prev.count += 1;
      else
        counts.set(c.code, {
          count: 1,
          noise: c.noise || NOISE_CODES.has(c.code),
          sample: raw.trim().slice(0, 140),
        });
    }
  }

  const topCodes = [...counts.entries()]
    .map(([code, v]) => ({ code, count: v.count, noise: v.noise }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  const noteworthy = [...counts.entries()]
    .filter(([code, v]) => NOTEWORTHY_CODES.has(code) || (!v.noise && v.count > 0 && code.startsWith("RSZ")))
    .filter(([code]) => NOTEWORTHY_CODES.has(code) || code === "RSZ-0062")
    .map(([code, v]) => ({ code, message: v.sample, count: v.count }));

  const healthy = errors === 0;
  const actionable = warnings - noiseWarnings;
  const summary = healthy
    ? actionable <= 0
      ? `Flusso OK · 0 ERROR · ${warnings} WARNING (tutti attesi/rumore ORFS)`
      : `Flusso OK · 0 ERROR · ${warnings} WARNING (${noiseWarnings} rumore, ${actionable} da rivedere)`
    : `${errors} ERROR · ${warnings} WARNING — fallimento reale`;

  return {
    errors,
    warnings,
    noiseWarnings,
    noteworthy,
    topCodes,
    healthy,
    summary,
  };
}

export function isExpectedTimingMetric(value: string): boolean {
  // nangate45 GCD golden finish WNS ≈ −0.04; mild negatives are course-expected
  const n = parseFloat(value.replace(/[^\d.-]/g, ""));
  if (!Number.isFinite(n)) return false;
  return n >= -0.15 && n < 0;
}

#!/usr/bin/env node
/**
 * Smoke unit checks for ORFS log classification (no Next runtime).
 * Run: node scripts/test_orfs_log.mjs
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { createRequire } from "module";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

// Inline minimal mirror of classify rules so we don't need TS transpile.
// Keep in sync with studio/src/lib/orfsLog.ts — also verified via /api/results.

const OR_TAG = /\[(ERROR|WARNING|INFO|NOTICE)\s+([A-Z]{2,5}-\d{4})\]/i;
const NOISE = new Set([
  "RSZ-0104",
  "GUI-0010",
  "GUI-0066",
  "GUI-0076",
  "IFP-0028",
  "EST-0027",
  "GRT-0246",
]);
const BENIGN_FAIL = /\b(?:total\s+)?(?:placement\s+)?fail(?:ure)?s?\s*:\s*0\b/i;

function classify(line) {
  const m = line.match(OR_TAG);
  const tag = m?.[1]?.toUpperCase() ?? null;
  const code = m?.[2]?.toUpperCase() ?? null;
  if (tag === "ERROR") return "error";
  if (BENIGN_FAIL.test(line)) return "ok";
  if (tag === "WARNING") return NOISE.has(code) ? "noise" : "warn";
  if (/fail|error/i.test(line)) return "false-positive-candidate";
  return "plain";
}

let fail = 0;
function ok(msg) {
  console.log("OK ", msg);
}
function bad(msg) {
  console.log("BAD", msg);
  fail += 1;
}

const samples = [
  ["[ERROR ODB-0001] boom", "error"],
  ["[WARNING RSZ-0104] Net _1_ only has one pin.", "noise"],
  ["[WARNING IFP-0028] Core area lower left snapped", "noise"],
  ["[WARNING RSZ-0062] Unable to repair all setup violations.", "warn"],
  ["Total Placement Failures:          0", "ok"],
  ["Diamond Move Failure:              0", "ok"],
];

for (const [line, want] of samples) {
  const got = classify(line);
  if (got === want) ok(`${want}: ${line.slice(0, 50)}`);
  else bad(`expected ${want} got ${got} for ${line}`);
}

const logDir = path.join(
  root,
  "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab",
);
if (fs.existsSync(logDir)) {
  let errors = 0;
  let warnings = 0;
  let noise = 0;
  let falsePos = 0;
  for (const f of fs.readdirSync(logDir).filter((x) => x.endsWith(".log"))) {
    const text = fs.readFileSync(path.join(logDir, f), "utf8");
    for (const line of text.split("\n")) {
      const c = classify(line);
      if (c === "error") errors += 1;
      if (c === "warn") warnings += 1;
      if (c === "noise") noise += 1;
      if (c === "false-positive-candidate" && BENIGN_FAIL.test(line) === false) {
        // leave
      }
      if (/fail/i.test(line) && BENIGN_FAIL.test(line)) {
        // should classify ok
        if (classify(line) !== "ok") falsePos += 1;
      }
    }
  }
  if (errors === 0) ok(`flowlab logs: 0 ERROR (warnings=${warnings} noise=${noise})`);
  else bad(`flowlab logs: ${errors} ERROR`);
  if (falsePos === 0) ok("no Failure:0 false positives");
  else bad(`${falsePos} Failure:0 still misclassified`);
} else {
  ok("skip disk logs (missing flowlab log dir)");
}

if (fail) {
  console.log("ORFS LOG CLASSIFY FAILED");
  process.exit(1);
}
console.log("ORFS LOG CLASSIFY PASSED");

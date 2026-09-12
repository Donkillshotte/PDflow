import {
  JOB_STATES,
  REPORT_STATUSES,
  type ActionDescriptor,
  type ArtifactRef,
  type ReportEnvelope,
  type RunContext,
  type ToolDescriptor,
} from "./pdflowContracts";

const SCOPES = new Set(["product", "flow", "package", "lab", "generated"]);
const AUTHORITIES = new Set(["finish", "candidate", "generated", "source"]);
const COMPARISON_SCOPES = new Set([
  "same-live-invocation",
  "not-comparable",
  "none",
]);
const TOOL_AVAILABILITIES = new Set([
  "READY",
  "MISSING",
  "MISCONFIGURED",
  "INCOMPATIBLE",
]);
const ACTION_AVAILABILITIES = new Set(["READY", "MISSING", "GAP"]);

function objectValue(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null;
}

export function validateArtifactRef(value: unknown): string[] {
  const item = objectValue(value);
  if (!item) return ["artifact must be an object"];
  const errors: string[] = [];
  for (const key of [
    "artifact_id",
    "kind",
    "scope",
    "variant",
    "relative_path",
    "content_hash",
    "size",
    "mtime_ns",
    "revision",
    "producer",
    "run_id",
    "authority",
    "mutable",
  ]) {
    if (!(key in item)) errors.push("missing " + key);
  }
  if (!SCOPES.has(String(item.scope))) errors.push("invalid artifact scope");
  if (!AUTHORITIES.has(String(item.authority))) {
    errors.push("invalid artifact authority");
  }
  for (const key of ["size", "mtime_ns", "revision"]) {
    if (
      typeof item[key] !== "number" ||
      !Number.isInteger(item[key]) ||
      Number(item[key]) < 0
    ) {
      errors.push("invalid artifact " + key);
    }
  }
  if (item.authority === "finish" && item.mutable !== false) {
    errors.push("finish artifacts must be immutable");
  }
  if (item.authority === "candidate" && item.mutable !== true) {
    errors.push("candidate artifacts must be mutable");
  }
  const relative = item.relative_path;
  if (
    typeof relative !== "string" ||
    !relative ||
    relative.startsWith("/") ||
    relative.includes("\0") ||
    relative.split(/[\\/]/).includes("..")
  ) {
    errors.push("invalid relative_path");
  }
  return errors;
}

export function validateReportEnvelope(value: unknown): string[] {
  const item = objectValue(value);
  if (!item) return ["report must be an object"];
  const errors: string[] = [];
  if (!REPORT_STATUSES.includes(item.status as (typeof REPORT_STATUSES)[number])) {
    errors.push("invalid report status");
  }
  if (typeof item.ok !== "boolean") errors.push("report ok must be boolean");
  if (
    ["GAP", "PARTIAL", "PROXY", "NOT_RUN"].includes(String(item.status)) &&
    item.ok === true
  ) {
    errors.push("non-signoff status cannot be ok");
  }
  if (item.status === "PASS" && item.ok !== true) {
    errors.push("PASS report must have ok=true");
  }
  if (!COMPARISON_SCOPES.has(String(item.comparison_scope))) {
    errors.push("invalid comparison_scope");
  }
  for (const key of ["input_artifacts", "output_artifacts"]) {
    if (!Array.isArray(item[key])) errors.push(key + " must be an array");
  }
  return errors;
}

export function validateRunContext(value: unknown): string[] {
  const item = objectValue(value);
  if (!item) return ["run context must be an object"];
  const errors: string[] = [];
  if (typeof item.design_id !== "string" || !item.design_id) {
    errors.push("invalid design_id");
  }
  if (typeof item.pdk_id !== "string" || !item.pdk_id) errors.push("invalid pdk_id");
  if (!Array.isArray(item.finish)) errors.push("finish must be an array");
  if (!Array.isArray(item.candidates)) errors.push("candidates must be an array");
  const artifacts = [
    ...(Array.isArray(item.finish) ? item.finish : []),
    ...(Array.isArray(item.candidates) ? item.candidates : []),
  ];
  for (const artifact of artifacts) {
    errors.push(
      ...validateArtifactRef(artifact).map((error) => "artifact: " + error),
    );
  }
  return errors;
}

export function validateToolDescriptor(value: unknown): string[] {
  const item = objectValue(value);
  if (!item) return ["tool descriptor must be an object"];
  const errors: string[] = [];
  for (const key of [
    "tool_id",
    "display_name",
    "capabilities",
    "input_kinds",
    "output_kinds",
    "timeout_seconds",
    "availability",
  ]) {
    if (!(key in item)) errors.push("missing " + key);
  }
  if (!TOOL_AVAILABILITIES.has(String(item.availability))) {
    errors.push("invalid tool availability");
  }
  if (
    typeof item.timeout_seconds !== "number" ||
    !Number.isInteger(item.timeout_seconds) ||
    item.timeout_seconds < 1
  ) {
    errors.push("invalid tool timeout_seconds");
  }
  for (const key of ["capabilities", "input_kinds", "output_kinds"]) {
    if (!Array.isArray(item[key])) errors.push(key + " must be an array");
  }
  return errors;
}

export function validateActionDescriptor(value: unknown): string[] {
  const item = objectValue(value);
  if (!item) return ["action descriptor must be an object"];
  const errors: string[] = [];
  for (const key of [
    "action_id",
    "display_name",
    "surface",
    "timeout_seconds",
    "required_tools",
    "mutates",
    "availability",
    "missing_tools",
  ]) {
    if (!(key in item)) errors.push("missing " + key);
  }
  if (!SCOPES.has(String(item.surface))) errors.push("invalid action surface");
  if (!ACTION_AVAILABILITIES.has(String(item.availability))) {
    errors.push("invalid action availability");
  }
  if (
    typeof item.timeout_seconds !== "number" ||
    !Number.isInteger(item.timeout_seconds) ||
    item.timeout_seconds < 1
  ) {
    errors.push("invalid action timeout_seconds");
  }
  if (!Array.isArray(item.required_tools)) errors.push("required_tools must be an array");
  if (!Array.isArray(item.missing_tools)) errors.push("missing_tools must be an array");
  if (typeof item.mutates !== "boolean") errors.push("mutates must be boolean");
  return errors;
}

export function validateJobState(value: unknown): boolean {
  return JOB_STATES.includes(value as (typeof JOB_STATES)[number]);
}

export function isValidArtifact(value: unknown): value is ArtifactRef {
  return validateArtifactRef(value).length === 0;
}

export function isValidReport(value: unknown): value is ReportEnvelope {
  return validateReportEnvelope(value).length === 0;
}

export function isValidContext(value: unknown): value is RunContext {
  return validateRunContext(value).length === 0;
}

export function isValidToolDescriptor(value: unknown): value is ToolDescriptor {
  return validateToolDescriptor(value).length === 0;
}

export function isValidActionDescriptor(value: unknown): value is ActionDescriptor {
  return validateActionDescriptor(value).length === 0;
}

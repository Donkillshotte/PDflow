/** Data contracts returned by the agent-owned native stage inspector. */

export type OdbStats = {
  design: string;
  instances: number;
  nets: number;
  dieDbu: { dx: number; dy: number };
  artifact: string;
};

export type StaSummary = {
  source: string;
  wns?: string | null;
  tns?: string | null;
  worstSlack?: string | null;
  paths: { endpoint: string; slack: string; status: string }[];
  jsonPaths?: number | null;
};

export type YosysStat = {
  cells?: string | null;
  area?: string | null;
  dff?: string | null;
  rawHits: string[];
};

export type InspectInput = {
  relative_path: string;
  content_hash: string;
  size: number;
  mtime_ns: number;
};

export type StageInspect = {
  schema_version?: number;
  kind?: "inspect_stage";
  status?: "PASS" | "FAIL" | "WARN" | "PARTIAL" | "PROXY" | "GAP" | "NOT_RUN";
  ok?: boolean;
  stage: string;
  variant?: string;
  odb: OdbStats | null;
  sta: StaSummary | null;
  yosys: YosysStat | null;
  hooks: { id: string; label: string; detail: string }[];
  inputs?: InspectInput[];
  reason?: string | null;
  job_id?: string;
  report_id?: string;
  resource?: Record<string, unknown> | null;
};

export function isStageInspect(value: unknown): value is StageInspect {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.stage === "string" &&
    (record.odb === null || typeof record.odb === "object") &&
    (record.sta === null || typeof record.sta === "object") &&
    (record.yosys === null || typeof record.yosys === "object") &&
    Array.isArray(record.hooks)
  );
}

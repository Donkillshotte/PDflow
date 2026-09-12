import type { CheckEligibility, CheckPolicy } from "./pdflowContracts";

const STAGES = new Set([
  "rtl",
  "synth",
  "floorplan",
  "pdn",
  "place",
  "cts",
  "route",
  "finish",
  "package",
]);

const EMPTY_POLICY: CheckPolicy = {
  schema_version: 1,
  stage: "finish",
  variant: "flowlab",
  run_id: null,
  checks: [],
  stage_order: [],
  principle:
    "eligibility is derived from checkpoint artifacts and native dependencies; selecting a tab never launches a job",
};

export function isAnalysisStage(value: string): boolean {
  return STAGES.has(value);
}

export async function getCheckPolicy(
  stage: string,
  variant: string,
  runId?: string | null,
): Promise<CheckPolicy> {
  if (!isAnalysisStage(stage)) return { ...EMPTY_POLICY, stage };
  const query = new URLSearchParams({ stage, variant });
  if (runId) query.set("run_id", runId);
  // Browser callers use the Next facade so the local-agent URL and its
  // authentication headers remain server-owned.  The agent itself still
  // exposes /v1/checks for native clients and diagnostics.
  const response = await fetch("/api/checks?" + query.toString(), {
    cache: "no-store",
  });
  const remote = response.ok ? ((await response.json()) as CheckPolicy) : null;
  return remote && Array.isArray(remote.checks)
    ? remote
    : { ...EMPTY_POLICY, stage, variant, run_id: runId ?? null };
}

export function findCheck(
  policy: CheckPolicy | null,
  checkId: string,
): CheckEligibility | null {
  return policy?.checks.find((item) => item.check_id === checkId) ?? null;
}

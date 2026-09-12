import { NextResponse } from "next/server";
import { agentFetch } from "@/lib/agentClient";
import { preferredResultsVariant } from "@/lib/open";

export const dynamic = "force-dynamic";

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
const SAFE_VARIANT = /^(?:flowlab|learn|eco_scratch|lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9])$/;
const SAFE_RUN_ID = /^[A-Za-z0-9_.-]{8,100}$/;
const SAFE_CHECK_ID = /^[a-z0-9_]{2,80}$/;

export async function GET(req: Request) {
  const params = new URL(req.url).searchParams;
  const stage = params.get("stage") || "finish";
  if (!STAGES.has(stage)) {
    return NextResponse.json(
      { schema_version: 1, stage, evidence: [], reason: "invalid analysis checkpoint" },
      { status: 400 },
    );
  }
  const variant = params.get("variant") || preferredResultsVariant();
  if (!SAFE_VARIANT.test(variant)) {
    return NextResponse.json(
      { schema_version: 1, stage, evidence: [], reason: "invalid analysis variant" },
      { status: 400 },
    );
  }
  const runId = params.get("run_id");
  if (runId && !SAFE_RUN_ID.test(runId)) {
    return NextResponse.json(
      { schema_version: 1, stage, evidence: [], reason: "invalid run_id" },
      { status: 400 },
    );
  }
  const checkId = params.get("check_id");
  if (checkId && !SAFE_CHECK_ID.test(checkId)) {
    return NextResponse.json(
      { schema_version: 1, stage, evidence: [], reason: "invalid check_id" },
      { status: 400 },
    );
  }
  const query = new URLSearchParams({ stage, variant });
  if (runId) query.set("run_id", runId);
  if (checkId) query.set("check_id", checkId);
  const remote = await agentFetch(`/v1/evidence?${query.toString()}`);
  if (!remote) {
    return NextResponse.json(
      {
        schema_version: 1,
        stage,
        variant,
        run_id: runId || null,
        evidence: [],
        count: 0,
        reason: "evidence unavailable because the local agent is offline",
      },
      { status: 503 },
    );
  }
  return NextResponse.json(remote);
}

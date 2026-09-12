import fs from "fs";
import path from "path";
import { NextResponse } from "next/server";
import { REPO_ROOT } from "@/lib/course";
import { assertUnder } from "@/lib/pathGuard";

export const dynamic = "force-dynamic";

const RUN_ID_RE = /^[A-Za-z0-9_.-]{8,100}$/;

/**
 * Read the rich report of an isolated System PDN experiment.  Scenario
 * reports live below the agent-owned run directory and are intentionally not
 * mixed into /learn/sim/reports, which remains the canonical evidence view.
 */
export async function GET(req: Request) {
  const runId = new URL(req.url).searchParams.get("run_id") ?? "";
  if (!RUN_ID_RE.test(runId)) {
    return NextResponse.json({ error: "invalid run_id" }, { status: 400 });
  }

  const runRoot = path.join(REPO_ROOT, ".pdflow", "runs");
  const reportPath = assertUnder(
    runRoot,
    path.join(runRoot, runId, "system-pdn", "report.json"),
  );
  let stat: fs.Stats;
  try {
    stat = fs.lstatSync(reportPath);
  } catch {
    return NextResponse.json({ error: "scenario report not found" }, { status: 404 });
  }
  if (!stat.isFile()) {
    return NextResponse.json({ error: "scenario report not found" }, { status: 404 });
  }

  try {
    const report = JSON.parse(fs.readFileSync(reportPath, "utf8")) as {
      kind?: string;
    };
    if (report.kind !== "system_pdn") {
      return NextResponse.json(
        { error: "file is not a System PDN report" },
        { status: 422 },
      );
    }
    return NextResponse.json(report, {
      headers: { "Cache-Control": "no-store, must-revalidate" },
    });
  } catch {
    return NextResponse.json({ error: "invalid scenario report" }, { status: 422 });
  }
}

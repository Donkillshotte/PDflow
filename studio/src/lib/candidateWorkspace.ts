import fs from "fs";
import path from "path";
import { REPO_ROOT } from "./course";
import { assertUnder, normalizeCandidateRunId } from "./pathGuard";

/**
 * Resolve only a local-agent-created FlowLab candidate. A run id is never
 * treated as a free-form filesystem path and the manifest is part of the
 * authorization boundary for candidate previews and inspection.
 */
export function candidateOrfsRoot(runId: string): string {
  const id = normalizeCandidateRunId(runId);
  const runsRoot = path.join(REPO_ROOT, ".pdflow", "runs");
  const runRoot = assertUnder(runsRoot, path.join(runsRoot, id));
  const manifestPath = path.join(runRoot, "manifest.json");
  if (!fs.existsSync(manifestPath)) {
    throw new Error("REFUSED: candidate run does not exist");
  }
  try {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8")) as {
      profile?: string;
      surface?: string;
    };
    if (manifest.profile !== "flowlab-candidate" || manifest.surface !== "flow") {
      throw new Error("REFUSED: run is not a FlowLab candidate");
    }
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("REFUSED:")) throw error;
    throw new Error("REFUSED: candidate run manifest is invalid");
  }
  return assertUnder(runRoot, path.join(runRoot, "candidate", "orfs"));
}

export function candidateResultsRoot(runId: string): string {
  return path.join(candidateOrfsRoot(runId), "results/nangate45/gcd/flowlab");
}

export function candidateReportsRoot(runId: string): string {
  return path.join(candidateOrfsRoot(runId), "reports/nangate45/gcd/flowlab");
}

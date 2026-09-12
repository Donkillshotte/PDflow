import fs from "fs";
import crypto from "crypto";
import path from "path";
import { preferredResultsVariant, resultsDir } from "./open";
import { agentFetch } from "./agentClient";
import { LEARN_ROOT } from "./course";
import { discoverStudioTools } from "./pdflowRegistry";
import type { ArtifactRef, RunContext, Surface } from "./pdflowContracts";
import { isValidContext } from "./pdflowValidation";

const CURRENT_ARTIFACTS = [
  "1_synth.odb",
  "2_1_floorplan.odb",
  "2_4_floorplan_pdn.odb",
  "3_3_place_gp.odb",
  "3_5_place_dp.odb",
  "4_cts.odb",
  "5_1_grt.odb",
  "5_2_route.odb",
  "6_final.odb",
  "6_final.def",
  "6_final.v",
  "6_final.spef",
  "6_final.gds",
];

type CacheEntry = {
  size: number;
  mtimeNs: number;
  digest: string | null;
  artifact: ArtifactRef;
};

const hashCache = new Map<string, CacheEntry>();

function preferredAsap7Variant(): string {
  const report = path.join(LEARN_ROOT, "sim/reports/lab_asap7.json");
  try {
    const value = JSON.parse(fs.readFileSync(report, "utf8")) as { variant?: unknown };
    const variant = typeof value.variant === "string" ? value.variant : "";
    if (/^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$/.test(variant)) return variant;
  } catch {
    /* Use the deterministic reference below when the live report is absent. */
  }
  return "lab_asap7_gcd_tc_rvt_nldm_7p5";
}

function sha256File(file: string): string | null {
  try {
    return crypto
      .createHash("sha256")
      .update(fs.readFileSync(file))
      .digest("hex");
  } catch {
    return null;
  }
}

function artifactFor(file: string, variant: string): ArtifactRef | null {
  try {
    const stat = fs.statSync(file);
    const relative = path
      .relative(path.resolve(process.cwd(), ".."), file)
      .split(path.sep)
      .join("/");
    const previous = hashCache.get(file);
    const digest =
      previous &&
      previous.size === stat.size &&
      previous.mtimeNs === Math.trunc(stat.mtimeMs * 1_000_000)
        ? previous.digest
        : sha256File(file);
    const sameStamp =
      previous &&
      previous.size === stat.size &&
      previous.mtimeNs === Math.trunc(stat.mtimeMs * 1_000_000) &&
      previous.digest === digest;
    const identity = crypto
      .createHash("sha256")
      .update(relative + ":" + (digest || "missing"))
      .digest("hex");
    const name = path.basename(file);
    const artifact: ArtifactRef = {
      artifact_id: "artifact-" + identity.slice(0, 24),
      kind: name.endsWith(".odb")
        ? "odb"
        : name.endsWith(".gds")
          ? "gds"
          : name.endsWith(".spef")
            ? "spef"
            : name.endsWith(".v")
              ? "verilog"
              : name.endsWith(".def")
                ? "def"
                : "file",
      scope: "flow",
      variant,
      relative_path: relative,
      content_hash: digest,
      size: stat.size,
      mtime_ns: Math.trunc(stat.mtimeMs * 1_000_000),
      revision: previous
        ? previous.artifact.revision + (sameStamp ? 0 : 1)
        : 0,
      producer: "orfs",
      run_id: null,
      authority: name.startsWith("6_final.") ? "finish" : "source",
      mutable: !name.startsWith("6_final."),
    };
    hashCache.set(file, {
      size: stat.size,
      mtimeNs: Math.trunc(stat.mtimeMs * 1_000_000),
      digest,
      artifact,
    });
    return artifact;
  } catch {
    return null;
  }
}

export function fallbackContext(
  surface: Surface = "flow",
  variantOverride?: string,
): RunContext {
  const variant =
    variantOverride ||
    (surface === "lab" || surface === "package"
      ? preferredAsap7Variant()
      : preferredResultsVariant());
  const asap7 = variant.startsWith("lab_asap7_");
  const root = resultsDir(variant);
  const finish = CURRENT_ARTIFACTS.map((name) =>
    artifactFor(path.join(root, name), variant),
  ).filter((artifact): artifact is ArtifactRef => artifact !== null);
  const tools = discoverStudioTools();
  return {
    schema_version: 1,
    run_id: null,
    surface,
    design_id: "gcd",
    pdk_id: asap7 ? "asap7" : "nangate45",
    profile: asap7 ? "asap7-lab" : "live",
    finish,
    candidates: [],
    tool_versions: tools.tool_versions,
    finish_mutable: false,
    comparison_scope: "same-live-invocation",
    generated_at: new Date().toISOString(),
  };
}

export async function getStudioContext(
  surface: Surface = "flow",
): Promise<RunContext> {
  const remote = await agentFetch<unknown>(
    "/v1/context?surface=" + encodeURIComponent(surface),
  );
  return remote && isValidContext(remote)
    ? remote
    : fallbackContext(surface);
}

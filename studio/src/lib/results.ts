import fs from "fs";
import path from "path";
import { REPO_ROOT } from "./course";

export type ArtifactInfo = {
  name: string;
  rel: string;
  exists: boolean;
  size: number;
  mtime: string | null;
};

export type MetricHit = {
  label: string;
  value: string;
  source: string;
};

export type StageResults = {
  stage: string;
  artifacts: ArtifactInfo[];
  metrics: MetricHit[];
  goldenHints: { label: string; value: string }[];
  variant?: string;
};

const DEFAULT_VARIANT = "learn";

function baseResults(variant = DEFAULT_VARIANT) {
  return path.join(
    /*turbopackIgnore: true*/ REPO_ROOT,
    `tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${variant}`,
  );
}
function baseReports(variant = DEFAULT_VARIANT) {
  return path.join(
    /*turbopackIgnore: true*/ REPO_ROOT,
    `tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/${variant}`,
  );
}
function baseLogs(variant = DEFAULT_VARIANT) {
  return path.join(
    /*turbopackIgnore: true*/ REPO_ROOT,
    `tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/${variant}`,
  );
}

const STAGE_ARTIFACTS: Record<string, string[]> = {
  synth: ["1_synth.odb", "1_2_yosys.v", "1_synth.sdc"],
  floorplan: [
    "2_floorplan.odb",
    "2_1_floorplan.odb",
    "2_4_floorplan_pdn.odb",
  ],
  place: [
    "3_place.odb",
    "3_3_place_gp.odb",
    "3_5_place_dp.odb",
  ],
  cts: ["4_cts.odb", "4_1_cts.odb"],
  route: ["5_route.odb", "5_1_grt.odb", "5_2_route.odb", "route.guide"],
  finish: [
    "6_final.gds",
    "6_final.odb",
    "6_final.spef",
    "6_final.def",
    "6_final.v",
    "6_final.sdc",
  ],
  check: [],
  status: [],
  list: [],
};

const STAGE_GOLDEN: Record<string, { label: string; value: string }[]> = {
  synth: [
    { label: "Celle", value: "496" },
    { label: "Area", value: "628.824" },
    { label: "DFF_X1", value: "35" },
  ],
  floorplan: [
    { label: "Core area", value: "1712.5 µm²" },
    { label: "Eff. util", value: "0.367" },
  ],
  place: [
    { label: "worst slack", value: "+0.01 ns" },
    { label: "period_min", value: "0.45 ns" },
    { label: "Design area", value: "684 µm² / 40%" },
  ],
  cts: [
    { label: "WNS", value: "−0.04 ns" },
    { label: "Inserted buffers", value: "45" },
    { label: "Util post", value: "48.3%" },
  ],
  route: [
    { label: "DRC lines", value: "0" },
    { label: "GRT WNS", value: "−0.05 ns" },
  ],
  finish: [
    { label: "WNS", value: "−0.04 ns" },
    { label: "TNS", value: "−0.60" },
    { label: "period_min", value: "0.50 ns (~2011 MHz)" },
  ],
};

function statFile(abs: string, name: string): ArtifactInfo {
  if (!fs.existsSync(abs)) {
    return { name, rel: name, exists: false, size: 0, mtime: null };
  }
  const st = fs.statSync(abs);
  return {
    name,
    rel: name,
    exists: true,
    size: st.size,
    mtime: st.mtime.toISOString(),
  };
}

function grepFile(abs: string, patterns: RegExp[], limit = 8): MetricHit[] {
  if (!fs.existsSync(abs)) return [];
  const text = fs.readFileSync(abs, "utf8");
  const hits: MetricHit[] = [];
  for (const line of text.split("\n")) {
    for (const re of patterns) {
      if (re.test(line)) {
        hits.push({
          label: re.source.slice(0, 40),
          value: line.trim().slice(0, 160),
          source: path.basename(abs),
        });
      }
    }
    if (hits.length >= limit) break;
  }
  return hits;
}

export function collectStageResults(
  stage: string,
  variant: string = DEFAULT_VARIANT,
): StageResults {
  const names = STAGE_ARTIFACTS[stage] ?? [];
  const artifacts = names.map((n) => {
    // reports live under reports/ for some names
    if (n.endsWith(".rpt") || n === "synth_stat.txt") {
      return statFile(path.join(baseReports(variant), n), n);
    }
    return statFile(path.join(baseResults(variant), n), n);
  });

  const metrics: MetricHit[] = [];
  if (stage === "synth") {
    metrics.push(
      ...grepFile(path.join(baseReports(variant), "synth_stat.txt"), [
        /Number of cells/i,
        /Chip area/i,
        /DFF_X1/,
      ]),
    );
  }
  if (stage === "floorplan") {
    metrics.push(
      ...grepFile(path.join(baseLogs(variant), "2_1_floorplan.log"), [
        /Core area/i,
        /Effective utilization/i,
        /Design area/i,
      ]),
    );
  }
  if (stage === "place") {
    metrics.push(
      ...grepFile(path.join(baseReports(variant), "3_resizer.rpt"), [
        /worst slack/i,
        /period_min/i,
        /setup violation/i,
      ]),
      ...grepFile(path.join(baseLogs(variant), "3_4_place_resized.log"), [
        /Design area/i,
      ]),
    );
  }
  if (stage === "cts") {
    metrics.push(
      ...grepFile(path.join(baseReports(variant), "4_cts_final.rpt"), [
        /worst slack/i,
        /setup violation/i,
        /skew/i,
      ]),
      ...grepFile(path.join(baseLogs(variant), "4_1_cts.log"), [
        /Inserted/i,
        /DPL-0006/,
        /RSZ-0062/,
        /DPL-0038/,
      ]),
    );
  }
  if (stage === "route") {
    const drc = path.join(baseReports(variant), "5_route_drc.rpt");
    if (fs.existsSync(drc)) {
      const lines = fs.readFileSync(drc, "utf8").split("\n").filter(Boolean).length;
      metrics.push({
        label: "DRC wc -l",
        value: String(lines),
        source: "5_route_drc.rpt",
      });
    }
    metrics.push(
      ...grepFile(path.join(baseReports(variant), "5_global_route.rpt"), [
        /worst slack/i,
        /setup violation/i,
      ]),
    );
  }
  if (stage === "finish") {
    metrics.push(
      ...grepFile(path.join(baseReports(variant), "6_finish.rpt"), [
        /wns max/i,
        /tns max/i,
        /period_min/i,
        /setup violation/i,
        /setup skew/i,
      ]),
    );
  }

  return {
    stage,
    artifacts,
    metrics: metrics.slice(0, 12),
    goldenHints: STAGE_GOLDEN[stage] ?? [],
    variant,
  };
}

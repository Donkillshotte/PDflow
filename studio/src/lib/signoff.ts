import fs from "fs";
import path from "path";
import { LEARN_ROOT, REPO_ROOT } from "./course";
import { resultsDir } from "./open";

export type SignoffPillarId = "timing" | "geometry" | "equivalence" | "power" | "pkg" | "thermal";

export type SignoffPillarStatus = "active" | "planned" | "proxy";

export type SignoffCheckDef = {
  id: string;
  label: string;
  action: string;
  script: string;
  reportRel: string;
  stampRel?: string;
  suiteHookId?: string;
  long?: boolean;
};

export type SignoffPillarDef = {
  id: SignoffPillarId;
  label: string;
  description: string;
  status: SignoffPillarStatus;
  orchestratorAction: string;
  checks: SignoffCheckDef[];
};

export const SIGNOFF_PILLARS: SignoffPillarDef[] = [
  {
    id: "timing",
    label: "Timing (STA)",
    description: "WNS/TNS/period_min vs golden-metrics post-SPEF",
    status: "active",
    orchestratorAction: "sta_signoff",
    checks: [
      {
        id: "sta_finish",
        label: "STA signoff",
        action: "sta_signoff",
        script: "learn/scripts/run_sta_signoff.sh",
        reportRel: "sim/reports/sta_signoff_{variant}.json",
        suiteHookId: "sta_signoff",
      },
    ],
  },
  {
    id: "geometry",
    label: "Geometria (DRC)",
    description: "Route DRC + KLayout GDS DRC",
    status: "active",
    orchestratorAction: "drc_signoff",
    checks: [
      {
        id: "drc_unified",
        label: "DRC signoff",
        action: "drc_signoff",
        script: "learn/scripts/run_drc_signoff.sh",
        reportRel: "sim/reports/drc_signoff_{variant}.json",
        suiteHookId: "drc_signoff",
        long: true,
      },
    ],
  },
  {
    id: "equivalence",
    label: "Equivalenza (LVS)",
    description: "GDS vs CDL via ORFS make lvs",
    status: "active",
    orchestratorAction: "klayout_lvs",
    checks: [
      {
        id: "lvs_gds_cdl",
        label: "LVS signoff",
        action: "klayout_lvs",
        script: "learn/scripts/run_klayout_lvs.sh",
        reportRel: "sim/reports/lvs_signoff_{variant}.json",
        stampRel: ".lvs.ok",
        suiteHookId: "lvs_signoff",
        long: true,
      },
    ],
  },
  {
    id: "power",
    label: "Power / PKG",
    description: "Activity → chip IR → System PDN → export lab",
    status: "active",
    orchestratorAction: "power_signoff",
    checks: [
      {
        id: "activity",
        label: "Activity → power",
        action: "activity_power",
        script: "learn/scripts/run_activity_power.sh",
        reportRel: "sim/reports/activity_power_{variant}.log",
      },
      {
        id: "chip_ir",
        label: "Chip IR mesh",
        action: "chip_pdn_ir",
        script: "learn/scripts/run_chip_pdn_ir.sh",
        reportRel: "sim/reports/pdn_chip_ir_{variant}.json",
        stampRel: ".chip_pdn_ir.ok",
        long: true,
      },
      {
        id: "system_pdn",
        label: "System PDN",
        action: "system_pdn",
        script: "learn/scripts/run_system_pdn.sh",
        reportRel: "sim/reports/system_pdn_{variant}.json",
        stampRel: ".system_pdn.ok",
      },
      {
        id: "mesh_export",
        label: "SPICE lab export",
        action: "export_spice_lab",
        script: "learn/scripts/export_spice_lab.sh",
        reportRel: "sim/spice/INDEX_{variant}.md",
      },
    ],
  },
];

/** Fase 2 — registry predisposto, script in arrivo (extended-flow §8–9). */
export const SIGNOFF_PLANNED_PILLARS: SignoffPillarDef[] = [
  {
    id: "pkg",
    label: "Packaging (bump/RDL)",
    description: "assign_io_bump · rdl_route · System PDN profondo",
    status: "planned",
    orchestratorAction: "pkg_signoff",
    checks: [
      {
        id: "bump_assign",
        label: "IO bump assignment",
        action: "pkg_bump",
        script: "learn/scripts/run_pkg_bump.sh",
        reportRel: "sim/reports/pkg_bump_{variant}.json",
      },
      {
        id: "rdl_route",
        label: "RDL routing",
        action: "pkg_rdl",
        script: "learn/scripts/run_pkg_rdl.sh",
        reportRel: "sim/reports/pkg_rdl_{variant}.json",
      },
    ],
  },
  {
    id: "thermal",
    label: "Thermal (proxy)",
    description: "Power map + IR → hotspot proxy · HotSpot future",
    status: "proxy",
    orchestratorAction: "thermal_signoff",
    checks: [
      {
        id: "thermal_proxy",
        label: "Thermal proxy signoff",
        action: "thermal_signoff",
        script: "learn/scripts/run_thermal_signoff.sh",
        reportRel: "sim/reports/thermal_signoff_{variant}.json",
      },
    ],
  },
];

export const ALL_SIGNOFF_PILLARS = [...SIGNOFF_PILLARS, ...SIGNOFF_PLANNED_PILLARS];

export const SIGNOFF_ORCHESTRATOR = {
  id: "signoff_all",
  label: "Signoff completo",
  action: "signoff_all",
  script: "learn/scripts/run_signoff_all.sh",
  reportRel: "sim/reports/signoff_all_{variant}.json",
  logRel: "sim/reports/signoff_all_{variant}.log",
  long: true,
} as const;

export const SIGNOFF_PHASE2_ORCHESTRATOR = {
  id: "signoff_phase2",
  label: "Signoff Fase 2",
  action: "signoff_phase2",
  script: "learn/scripts/run_signoff_phase2.sh",
  reportRel: "sim/reports/signoff_phase2_{variant}.json",
  logRel: "sim/reports/signoff_phase2_{variant}.log",
  long: false,
} as const;

export {
  SIGNOFF_ACTIONS,
  PHASE2_SIGNOFF_ACTIONS,
  type SignoffAction,
  type Phase2SignoffAction,
  isSignoffAction,
  isPhase2SignoffAction,
} from "./actions";

export function signoffPillar(id: SignoffPillarId): SignoffPillarDef | undefined {
  return SIGNOFF_PILLARS.find((p) => p.id === id);
}

export function reportPathForCheck(check: SignoffCheckDef, variant: string): string {
  return path.join(LEARN_ROOT, check.reportRel.replace("{variant}", variant));
}

const GOLDEN_PATH = path.join(LEARN_ROOT, "signoff/golden-gcd.json");

export function readGoldenGcd(): Record<string, unknown> | null {
  try {
    if (!fs.existsSync(GOLDEN_PATH)) return null;
    return JSON.parse(fs.readFileSync(GOLDEN_PATH, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export type SignoffGate = {
  id: string;
  pillar: SignoffPillarId;
  label: string;
  ok: boolean;
  detail?: string;
  action?: string;
};

function pillarReportPath(pillarId: SignoffPillarId, variant: string): string {
  const map: Partial<Record<SignoffPillarId, string>> = {
    timing: `sim/reports/sta_signoff_${variant}.json`,
    geometry: `sim/reports/drc_signoff_${variant}.json`,
    equivalence: `sim/reports/lvs_signoff_${variant}.json`,
    power: `sim/reports/power_signoff_${variant}.json`,
    thermal: `sim/reports/thermal_signoff_${variant}.json`,
    pkg: `sim/reports/pkg_signoff_${variant}.json`,
  };
  const rel = map[pillarId];
  return rel ? path.join(LEARN_ROOT, rel) : "";
}

export type SignoffCheckEval = {
  id: string;
  label: string;
  actual: unknown;
  target: unknown;
  ok: boolean;
  note?: string;
};

export function readPillarReportEval(
  pillarId: SignoffPillarId,
  variant: string,
): {
  ok?: boolean;
  summary?: string;
  checks: SignoffCheckEval[];
  artifactParse?: Record<string, unknown>;
} | null {
  const abs = pillarReportPath(pillarId, variant);
  if (!abs) return null;
  const report = readJsonReport(abs);
  if (!report) return null;
  const evaluation = (report.evaluation ?? {}) as { checks?: SignoffCheckEval[] };
  return {
    ok: report.ok as boolean | undefined,
    summary: report.summary as string | undefined,
    checks: evaluation.checks ?? [],
    artifactParse: report.artifact_parse as Record<string, unknown> | undefined,
  };
}

function readJsonReport(abs: string): Record<string, unknown> | null {
  try {
    if (!fs.existsSync(abs)) return null;
    return JSON.parse(fs.readFileSync(abs, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function evaluateSignoffGates(variant = "flowlab"): {
  ok: boolean;
  gates: SignoffGate[];
  pillars: Record<string, { ok: boolean; report?: string }>;
} {
  const gates: SignoffGate[] = [];
  const pillars: Record<string, { ok: boolean; report?: string }> = {};

  for (const pillar of SIGNOFF_PILLARS) {
    const orchRel = pillar.checks[0]?.reportRel.replace("{variant}", variant) ?? "";
    const orchReport =
      pillar.id === "timing"
        ? readJsonReport(path.join(LEARN_ROOT, `sim/reports/sta_signoff_${variant}.json`))
        : pillar.id === "geometry"
          ? readJsonReport(path.join(LEARN_ROOT, `sim/reports/drc_signoff_${variant}.json`))
          : pillar.id === "equivalence"
            ? readJsonReport(path.join(LEARN_ROOT, `sim/reports/lvs_signoff_${variant}.json`))
            : readJsonReport(path.join(LEARN_ROOT, `sim/reports/power_signoff_${variant}.json`));

    const pillarOk = orchReport?.ok === true;
    pillars[pillar.id] = {
      ok: pillarOk,
      report: orchReport ? `sim/reports/${pillar.orchestratorAction}_${variant}.json` : undefined,
    };

    gates.push({
      id: pillar.id,
      pillar: pillar.id,
      label: pillar.label,
      ok: pillarOk,
      detail: orchReport
        ? (orchReport.summary as string) || (pillarOk ? "report ok" : "soglie golden")
        : "report assente — esegui signoff",
      action: pillar.orchestratorAction,
    });

    for (const check of pillar.checks) {
      const rel = check.reportRel.replace("{variant}", variant);
      const abs = path.join(LEARN_ROOT, rel);
      const exists = fs.existsSync(abs);
      let stampOk = true;
      if (check.stampRel) {
        stampOk = fs.existsSync(path.join(resultsDir(variant), check.stampRel));
      }
      gates.push({
        id: `${pillar.id}_${check.id}`,
        pillar: pillar.id,
        label: check.label,
        ok: exists && stampOk,
        detail: exists
          ? stampOk
            ? rel
            : `manca stamp ${check.stampRel}`
          : "artefatto assente",
        action: check.action,
      });
    }
  }

  const allReport = readJsonReport(
    path.join(LEARN_ROOT, `sim/reports/signoff_all_${variant}.json`),
  );
  gates.push({
    id: "signoff_all",
    pillar: "timing",
    label: "Signoff completo",
    ok: allReport?.ok === true,
    detail: allReport ? String(allReport.summary ?? "signoff_all") : "non eseguito",
    action: SIGNOFF_ORCHESTRATOR.action,
  });

  const pillarGates = gates.filter((g) => SIGNOFF_PILLARS.some((p) => p.id === g.id));
  return {
    ok: pillarGates.every((g) => g.ok) && allReport?.ok !== false,
    gates,
    pillars,
  };
}

export function signoffMatrixForUi(variant = "flowlab") {
  return {
    variant,
    golden: readGoldenGcd(),
    pillars: SIGNOFF_PILLARS.map((p) => ({
      ...p,
      reportEval: readPillarReportEval(p.id, variant),
      checks: p.checks.map((c) => ({
        ...c,
        reportPath: c.reportRel.replace("{variant}", variant),
        reportExists: fs.existsSync(reportPathForCheck(c, variant)),
      })),
    })),
    plannedPillars: SIGNOFF_PLANNED_PILLARS.map((p) => ({
      ...p,
      reportEval: readPillarReportEval(p.id, variant),
    })),
    orchestrator: {
      ...SIGNOFF_ORCHESTRATOR,
      reportPath: SIGNOFF_ORCHESTRATOR.reportRel.replace("{variant}", variant),
      reportExists: fs.existsSync(
        path.join(LEARN_ROOT, SIGNOFF_ORCHESTRATOR.reportRel.replace("{variant}", variant)),
      ),
    },
    evaluation: evaluateSignoffGates(variant),
  };
}

export function repoScriptAbs(rel: string): string {
  return path.join(REPO_ROOT, rel);
}

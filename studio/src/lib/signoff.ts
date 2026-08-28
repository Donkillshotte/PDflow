import fs from "fs";
import path from "path";
import { LEARN_ROOT, REPO_ROOT } from "./course";
import { resultsDir } from "./open";

export type SignoffPillarId = "timing" | "geometry" | "equivalence" | "power";

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
  orchestratorAction: string;
  checks: SignoffCheckDef[];
};

export const SIGNOFF_PILLARS: SignoffPillarDef[] = [
  {
    id: "timing",
    label: "Timing (STA)",
    description: "WNS/TNS/period_min vs golden-metrics post-SPEF",
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

export const SIGNOFF_ORCHESTRATOR = {
  id: "signoff_all",
  label: "Signoff completo",
  action: "signoff_all",
  script: "learn/scripts/run_signoff_all.sh",
  reportRel: "sim/reports/signoff_all_{variant}.json",
  logRel: "sim/reports/signoff_all_{variant}.log",
  long: true,
} as const;

export const SIGNOFF_ACTIONS = [
  "sta_signoff",
  "drc_signoff",
  "klayout_lvs",
  "power_signoff",
  "signoff_all",
] as const;

export type SignoffAction = (typeof SIGNOFF_ACTIONS)[number];

export function isSignoffAction(action: string): action is SignoffAction {
  return (SIGNOFF_ACTIONS as readonly string[]).includes(action);
}

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
      checks: p.checks.map((c) => ({
        ...c,
        reportPath: c.reportRel.replace("{variant}", variant),
        reportExists: fs.existsSync(reportPathForCheck(c, variant)),
      })),
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

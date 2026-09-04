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
    description: "WNS/TNS/period_min vs golden-metrics post-SPEF; optional educational IR-aware overlay",
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
      {
        id: "sta_ir",
        label: "STA IR-aware",
        action: "sta_ir_aware",
        script: "learn/scripts/run_sta_ir_aware.sh",
        reportRel: "sim/reports/sta_ir_aware_{variant}.json",
        suiteHookId: "sta_ir_aware",
      },
    ],
  },
  {
    id: "geometry",
    label: "Geometry (DRC)",
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
    label: "Equivalence (LVS)",
    description: "GDS vs filtered CDL (FILL from DEF, wells → VDD/VSS)",
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
    label: "Power",
    description: "Activity → chip IR → system droop. System PDN / Phase 2 stay on /pkg.",
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
        id: "vectorless",
        label: "Vectorless / dynamic IR",
        action: "vectorless",
        script: "learn/scripts/run_vectorless.sh",
        reportRel: "sim/reports/vectorless_{variant}.json",
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
        id: "vyges_em_ir",
        label: "vyges-em-ir",
        action: "vyges_em_ir",
        script: "learn/scripts/run_vyges_em_ir.sh",
        reportRel: "sim/reports/vyges_em_ir_{variant}.json",
        stampRel: ".vyges_em_ir.ok",
      },
      {
        id: "dynamic_ir",
        label: "Dynamic IR I(t)",
        action: "dynamic_ir",
        script: "learn/scripts/run_dynamic_ir.sh",
        reportRel: "sim/reports/dynamic_ir_{variant}_direct.json",
        stampRel: ".dynamic_ir.ok",
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

/** Phase 2 — packaging + HotSpot thermal (extended-flow §8–9). */
export const SIGNOFF_PLANNED_PILLARS: SignoffPillarDef[] = [
  {
    id: "pkg",
    label: "Packaging (bump/RDL)",
    description: "Bump mesh + system PDN + dummy rdl_route on a sidecar ODB (not C4).",
    status: "active",
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
    label: "Thermal (HotSpot)",
    description: "UVA HotSpot architecture compact model (°C). Not Ansys / not foundry.",
    status: "active",
    orchestratorAction: "thermal_signoff",
    checks: [
      {
        id: "thermal_hotspot",
        label: "HotSpot t_max (°C)",
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
  label: "Full signoff",
  action: "signoff_all",
  script: "learn/scripts/run_signoff_all.sh",
  reportRel: "sim/reports/signoff_all_{variant}.json",
  logRel: "sim/reports/signoff_all_{variant}.log",
  long: true,
} as const;

export const SIGNOFF_PHASE2_ORCHESTRATOR = {
  id: "signoff_phase2",
  label: "Signoff Phase 2",
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

export type StaIrAwareSummary = {
  ok?: boolean;
  slack_ns?: number | null;
  slack_ir_ns?: number | null;
  n_joined?: number | null;
  n_gates?: number | null;
  degradation_ps?: number | null;
  worst_cell_ir_mv?: number | null;
  map?: string | null;
  path_gates?: Record<string, unknown>[];
  hottest_cells?: Record<string, unknown>[];
  note?: string;
  report?: string;
};

export function readStaIrAware(variant = "flowlab"): StaIrAwareSummary | null {
  const abs = path.join(LEARN_ROOT, `sim/reports/sta_ir_aware_${variant}.json`);
  const report = readJsonReport(abs);
  if (!report) return null;
  const sta = (report.sta ?? {}) as Record<string, unknown>;
  const ir = (report.ir ?? {}) as Record<string, unknown>;
  return {
    ok: report.ok as boolean | undefined,
    slack_ns: (sta.slack_ns as number | null | undefined) ?? null,
    slack_ir_ns: (sta.slack_ir_ns as number | null | undefined) ?? null,
    n_joined: (sta.n_joined as number | null | undefined) ?? null,
    n_gates: (sta.n_gates as number | null | undefined) ?? null,
    degradation_ps: (sta.degradation_ps as number | null | undefined) ?? null,
    worst_cell_ir_mv: (ir.worst_cell_ir_mv as number | null | undefined) ?? null,
    map: (ir.map as string | null | undefined) ?? null,
    path_gates: (report.path_gates as Record<string, unknown>[] | undefined) ?? [],
    hottest_cells: (report.hottest_cells as Record<string, unknown>[] | undefined) ?? [],
    note: (report.note as string | undefined) ?? undefined,
    report: `sim/reports/sta_ir_aware_${variant}.json`,
  };
}

/** LVS leftover circuits named in must-connect messages (e.g. DFF_X2). */
export function leftoverCircuitsFromReport(
  report: Record<string, unknown> | null,
): string[] {
  const parse = report?.artifact_parse as
    | { lvsdb?: { messages?: string[] } }
    | undefined;
  const messages = parse?.lvsdb?.messages ?? [];
  return Array.from(
    new Set(
      messages
        .map((m) => m.match(/circuit (\S+)/)?.[1])
        .filter((n): n is string => Boolean(n)),
    ),
  );
}

export function leftoverMustConnectDetail(
  report: Record<string, unknown> | null,
): string | null {
  if (!report) return null;
  const leftover = report.leftover as
    | { must_connect?: number; circuits?: string[] }
    | undefined;
  const mc = Number(leftover?.must_connect ?? report.must_connect ?? 0);
  if (!(mc > 0)) return null;
  const cells = leftover?.circuits?.length
    ? leftover.circuits.map(String)
    : leftoverCircuitsFromReport(report);
  const named = cells.length ? cells.join(", ") : "Nangate cell";
  return `leftover must-connect ${mc} (${named}, Nangate split wells)`;
}

function readJsonReport(abs: string): Record<string, unknown> | null {
  try {
    if (!fs.existsSync(abs)) return null;
    return JSON.parse(fs.readFileSync(abs, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function evaluateCheckGate(
  check: SignoffCheckDef,
  pillar: SignoffPillarId,
  variant: string,
): SignoffGate {
  const rel = check.reportRel.replace("{variant}", variant);
  const abs = path.join(LEARN_ROOT, rel);
  const exists = fs.existsSync(abs);
  const report = exists ? readJsonReport(abs) : null;
  let stampOk = true;
  if (check.stampRel) {
    stampOk = fs.existsSync(path.join(resultsDir(variant), check.stampRel));
  }
  if (report && typeof report.ok === "boolean") {
    let detail = String(report.summary ?? rel);
    if (check.id === "vyges_em_ir" && !detail.includes("em_checked")) {
      const vyges = (report.vyges as { em_checked?: number; ir_met?: boolean } | undefined) ?? {};
      const em = Number(vyges.em_checked ?? 0);
      detail += ` · em_checked ${em} (no foundry emlimit)`;
      if (vyges.ir_met === false) detail += " · ir_met false";
    }
    return {
      id: `${pillar}_${check.id}`,
      pillar,
      label: check.label,
      ok: report.ok === true,
      detail,
      action: check.action,
    };
  }
  if (check.stampRel) {
    return {
      id: `${pillar}_${check.id}`,
      pillar,
      label: check.label,
      ok: stampOk,
      detail: stampOk ? rel : `missing stamp ${check.stampRel}`,
      action: check.action,
    };
  }
  return {
    id: `${pillar}_${check.id}`,
    pillar,
    label: check.label,
    ok: exists,
    detail: exists ? rel : "artifact missing",
    action: check.action,
  };
}

export function evaluateSignoffGates(variant = "flowlab"): {
  ok: boolean;
  phase2Ok: boolean;
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

    let detail = orchReport
      ? (orchReport.summary as string) || (pillarOk ? "report ok" : "golden thresholds")
      : "report missing — run signoff";
    if (pillar.id === "equivalence" && orchReport) {
      const leftover = leftoverMustConnectDetail(orchReport);
      if (leftover && !String(detail).includes("leftover must-connect")) {
        detail += ` · ${leftover}`;
      }
    }
    if (pillar.id === "power" && orchReport?.ir_mesh_ledger) {
      detail += " · IR meshes not comparable (gold / chip / current_run / vyges / system)";
    }
    gates.push({
      id: pillar.id,
      pillar: pillar.id,
      label: pillar.label,
      ok: pillarOk,
      detail,
      action: pillar.orchestratorAction,
    });

    for (const check of pillar.checks) {
      gates.push(evaluateCheckGate(check, pillar.id, variant));
    }
  }

  const allReport = readJsonReport(
    path.join(LEARN_ROOT, `sim/reports/signoff_all_${variant}.json`),
  );
  gates.push({
    id: "signoff_all",
    pillar: "timing",
    label: "Full signoff",
    ok: allReport?.ok === true,
    detail: allReport ? String(allReport.summary ?? "signoff_all") : "not run",
    action: SIGNOFF_ORCHESTRATOR.action,
  });

  for (const pillar of SIGNOFF_PLANNED_PILLARS) {
    const abs = pillarReportPath(pillar.id, variant);
    const orchReport = abs ? readJsonReport(abs) : null;
    const pillarOk = orchReport?.ok === true;
    pillars[pillar.id] = {
      ok: pillarOk,
      report: orchReport ? abs.replace(LEARN_ROOT + path.sep, "").replace(/\\/g, "/") : undefined,
    };
    gates.push({
      id: pillar.id,
      pillar: pillar.id,
      label: pillar.label,
      ok: pillarOk,
      detail: orchReport
        ? (orchReport.summary as string) || (pillarOk ? "report ok" : "thresholds / proxy")
        : "report missing — run signoff Phase 2",
      action: pillar.orchestratorAction,
    });
    for (const check of pillar.checks) {
      gates.push(evaluateCheckGate(check, pillar.id, variant));
    }
  }

  const ph2Report = readJsonReport(
    path.join(LEARN_ROOT, `sim/reports/signoff_phase2_${variant}.json`),
  );
  gates.push({
    id: "signoff_phase2",
    pillar: "thermal",
    label: "Signoff Phase 2",
    ok: ph2Report?.ok === true,
    detail: ph2Report ? String(ph2Report.summary ?? "signoff_phase2") : "not run",
    action: SIGNOFF_PHASE2_ORCHESTRATOR.action,
  });

  const closeGates = gates.filter((g) => SIGNOFF_PILLARS.some((p) => p.id === g.id));
  const phase2Gates = gates.filter((g) =>
    SIGNOFF_PLANNED_PILLARS.some((p) => p.id === g.id),
  );
  const phase2Orch = gates.find((g) => g.id === "signoff_phase2");
  return {
    ok: closeGates.every((g) => g.ok) && allReport?.ok === true,
    phase2Ok: phase2Gates.every((g) => g.ok) && phase2Orch?.ok === true,
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
    staIr: readStaIrAware(variant),
    eco: readJsonReport(path.join(LEARN_ROOT, `sim/reports/eco_${variant}.json`)),
  };
}

export function repoScriptAbs(rel: string): string {
  return path.join(REPO_ROOT, rel);
}

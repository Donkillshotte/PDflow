/**
 * Lab bench snapshot for the current invocation.
 * No cross-invocation result is read here.
 */
import fs from "fs";
import path from "path";
import { LEARN_ROOT } from "./course";
import { currentDesignMtime, isCurrentAsap7Artifact, isCurrentRunArtifact } from "./liveReports";
import { readLiveRunDroopMv } from "./story";
import { evaluateLabAdmit, labPillarOf, type LabPillarEvidence } from "./labHonesty";

function readJson(rel: string): Record<string, unknown> | null {
  const p = path.join(LEARN_ROOT, rel);
  const labFinishDerived = new Set([
    "lab_asap7.json",
    "lab_asap7_folio.json",
    "lab_asap7_pkg.json",
    "lab_asap7_chip_pdn.json",
    "lab_asap7_lvs.json",
    "lab_asap7_mmmc.json",
    "lab_asap7_drc.json",
    "lab_asap7_thermal.json",
  ]);
  if (labFinishDerived.has(path.basename(p))) {
    if (!isCurrentAsap7Artifact(p)) return null;
  } else if (!isCurrentRunArtifact(p, "flowlab")) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(p, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function n(v: unknown): number | null {
  if (v == null || v === "") return null;
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

export type LabCheck = {
  id: string;
  design: string;
  ok: boolean;
  status: string;
  quantity: string;
  value: unknown;
  bound: string;
  note: string;
};

export type AxisDelta = {
  wnsPs: number | null;
  areaPct: number | null;
  powerPct: number | null;
  leakPct: number | null;
  irPct: number | null;
};

export type ExperimentPair = {
  design: string;
  clockNs: number;
  verdict: string;
  reference: { id: string; variant?: string; wnsNs: number | null; irMv: number | null; area: number | null; power: number | null; leak: number | null };
  cook: { id: string; variant?: string; wnsNs: number | null; irMv: number | null; area: number | null; power: number | null; leak: number | null; note?: string };
  versus: "same-invocation";
  delta: AxisDelta;
};

export function liveComparisons(): ExperimentPair[] {
  // A pair is returned only when the current report explicitly supplies one.
  // The controller currently exposes a single live snapshot, so there is no
  // implicit base or second invocation to compare against.
  return [];
}

export type LaunchShot = {
  role: string;
  variant: string;
  designId: string;
  createdAt: number | null;
  nCandidates: number | null;
  nF4: number | null;
  winningIrMv: number | null;
  winningStaticMv: number | null;
  champAmgMv: number | null;
  champWnsNs: number | null;
  spentS: number | null;
  summary: string;
  compare: {
    versus: number | null;
    sameMesh: boolean | null;
    note: string;
    delta: {
      n_candidates: number | null;
      winning_ir_pdn_mv: number | null;
      winning_static_mv: number | null;
      ir_cell_champ_wns_ns: number | null;
      spent_s: number | null;
    } | null;
  } | null;
};

function launchOf(row: Record<string, unknown>): LaunchShot {
  const cmp = (row.compare as Record<string, unknown>) || null;
  const delta = (cmp?.delta as Record<string, unknown>) || null;
  return {
    role: String(row.role ?? "cook"),
    variant: String(row.variant ?? "flowlab"),
    designId: String(row.design_id ?? "gcd"),
    createdAt: n(row.created_at),
    nCandidates: n(row.n_candidates),
    nF4: n(row.n_f4),
    winningIrMv: n(row.winning_ir_pdn_mv),
    winningStaticMv: n(row.winning_static_mv),
    champAmgMv: n(row.ir_champ_amg_mv),
    champWnsNs: n(row.ir_cell_champ_wns_ns),
    spentS: n(row.spent_s),
    summary: String(row.summary ?? ""),
    compare: cmp
      ? {
          versus: n(cmp.versus),
          sameMesh: cmp.same_mesh == null ? null : Boolean(cmp.same_mesh),
          note: String(cmp.note ?? ""),
          delta: delta
            ? {
                n_candidates: n(delta.n_candidates),
                winning_ir_pdn_mv: n(delta.winning_ir_pdn_mv),
                winning_static_mv: n(delta.winning_static_mv),
                ir_cell_champ_wns_ns: n(delta.ir_cell_champ_wns_ns),
                spent_s: n(delta.spent_s),
              }
            : null,
        }
      : null,
  };
}

export function getLabSnapshot() {
  const physics =
    readJson("sim/dse/lab_physics_ledger.json") || readJson("sim/reports/lab_physics_flowlab.json");
  const pairs = liveComparisons();
  const dse = readJson("sim/reports/dse_flowlab.json");
  const staIr = readJson("sim/reports/sta_ir_aware_flowlab.json");
  const sta = (staIr?.sta ?? {}) as Record<string, unknown>;
  const staIrMesh = (staIr?.ir ?? {}) as Record<string, unknown>;
  const liveLaunch = readJson("sim/dse/live_run_flowlab.json");
  const launches = liveLaunch ? [launchOf(liveLaunch)] : [];
  const thisLaunch = launches.length ? launches[launches.length - 1]! : null;
  return {
    title: "Lab bench",
    lead: "Numbers that survive a rail-scale and same-mesh check. Not foundry correlation.",
    runMv: readLiveRunDroopMv("flowlab"),
    physics: physics
      ? {
          ok: physics.ok === true,
          nReady: Number(physics.n_ready ?? 0),
          nChecks: Number(physics.n_checks ?? 0),
          watch: (physics.watch as string[]) ?? [],
          fail: (physics.fail as string[]) ?? [],
          gap: (physics.gap as string[]) ?? [],
          checks: (physics.checks as LabCheck[]) ?? [],
          slots: physics.slots ?? [],
          note: physics.note,
        }
      : null,
    staIr: {
      slackNs: n(sta.slack_ns),
      slackIrNs: n(sta.slack_ir_ns),
      nJoined: n(sta.n_joined),
      nGates: n(sta.n_gates),
      degradationPs: n(sta.degradation_ps),
      worstCellIrMv: n(staIrMesh.worst_cell_ir_mv),
      map: typeof staIrMesh.map === "string" ? staIrMesh.map : null,
    },
    dse: dse
      ? {
          ok: dse.ok === true,
          summary: String(dse.summary ?? ""),
          nCandidates: Number(dse.n_candidates ?? 0),
        }
      : null,
    comparisons: pairs,
    launches,
    thisLaunch,
    asap7: readAsap7Lab(),
  };
}

type Asap7Qor = {
  wnsPs: number | null;
  areaUm2: number | null;
  powerMw: number | null;
  leakageNw: number | null;
  irDropVddMv: number | null;
  periodMinPs: number | null;
  fmaxGhz: number | null;
  timingClosed: boolean;
};

function asap7QorOf(raw: Record<string, unknown> | null): Asap7Qor | null {
  if (!raw) return null;
  const q = (raw.qor as Record<string, unknown>) || raw;
  return {
    wnsPs: n(q.wns_ps),
    areaUm2: n(q.area_um2),
    powerMw: n(q.power_mw) ?? (n(q.power_w) != null ? n(q.power_w)! * 1e3 : null),
    leakageNw: n(q.leakage_nw) ?? (n(q.leakage_w) != null ? n(q.leakage_w)! * 1e9 : null),
    irDropVddMv: n(q.ir_drop_vdd_mv) ?? (n(q.ir_vdd_worst_v) != null ? n(q.ir_vdd_worst_v)! * 1e3 : null),
    periodMinPs: n(q.period_min_ps),
    fmaxGhz: n(q.fmax_ghz),
    timingClosed: q.timing_closed === true,
  };
}

function readAsap7Folio(): Record<string, unknown>[] {
  const raw = readJson("sim/reports/lab_asap7_folio.json");
  const cooks = raw?.cooks;
  return Array.isArray(cooks) ? (cooks as Record<string, unknown>[]) : [];
}

type Asap7ProxyReport = {
  name: string;
  report: Record<string, unknown>;
};

const ASAP7_PROXY_REPORT_RE = /^lab_asap7_bspdn_proxy(?:_[a-z0-9][a-z0-9_.+-]*)?\.json$/;
const LAB_ASAP7_VARIANT_RE = /^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$/;
const ASAP7_PROXY_MESH_RE = /^asap7_bspdn_proxy_[a-z0-9][a-z0-9_.+-]*$/;

function selfContainedProxyReport(report: Record<string, unknown>): boolean {
  const createdAt = report.created_at;
  const createdMs = typeof createdAt === "number" ? createdAt * 1000 : Date.parse(String(createdAt ?? ""));
  return (
    (report.surface === "lab" || report.surface === "lab_asap7") &&
    report.platform === "asap7" &&
    typeof report.variant === "string" &&
    LAB_ASAP7_VARIANT_RE.test(report.variant) &&
    typeof report.run_id === "string" &&
    report.run_id.trim().length > 0 &&
    Number.isFinite(createdMs) &&
    typeof report.mesh_id === "string" &&
    ASAP7_PROXY_MESH_RE.test(report.mesh_id) &&
    report.product_win === false &&
    report.productWin === false &&
    report.comparable_to_gold_ir === false
  );
}

function currentProxyReport(abs: string, report: Record<string, unknown>): boolean {
  const variant = typeof report.variant === "string" ? report.variant : null;
  const variantValid = variant == null || LAB_ASAP7_VARIANT_RE.test(variant);
  if (variantValid && isCurrentAsap7Artifact(abs)) return true;
  // If this variant has a physical finish, the finish mtime is authoritative;
  // a self-contained proxy report cannot bypass a stale-result check.
  if (variant && LAB_ASAP7_VARIANT_RE.test(variant) && currentDesignMtime(variant) != null) return false;
  return selfContainedProxyReport(report);
}

/**
 * Read only the allowlisted ASAP7 BSPDN proxy report family. The payload still
 * has to pass the current-artifact check; a stale report never becomes a lab
 * badge merely because its filename matches.
 */
function readAsap7ProxyReport(): Asap7ProxyReport | null {
  const dir = path.join(LEARN_ROOT, "sim/reports");
  let names: string[];
  try {
    names = fs
      .readdirSync(dir)
      .filter((name) => ASAP7_PROXY_REPORT_RE.test(name))
      .sort();
  } catch {
    return null;
  }
  const current: { name: string; report: Record<string, unknown>; mtime: number }[] = [];
  for (const name of names) {
    const abs = path.join(dir, name);
    try {
      const report = JSON.parse(fs.readFileSync(abs, "utf8")) as Record<string, unknown>;
      // A proxy-only run has no ORFS finish directory to anchor against. Its
      // self-contained run id/timestamp and allowlisted mesh family are the
      // freshness boundary; finished ASAP7 reports still use the stronger
      // current-artifact check above.
      if (!currentProxyReport(abs, report)) continue;
      current.push({ name, report, mtime: fs.statSync(abs).mtimeMs });
    } catch {
      // A malformed candidate is simply not evidence.
    }
  }
  current.sort((a, b) => a.mtime - b.mtime);
  const latest = current[current.length - 1];
  return latest ? { name: latest.name, report: latest.report } : null;
}

/**
 * Project the current proxy report into the Lab-only /api/runs shape.
 * Product and suite callers do not use this path; resultsDir is rechecked
 * before it crosses the API boundary.
 */
export function getLabAsap7Runs() {
  const proxy = readAsap7ProxyReport();
  if (!proxy) return { runs: [], surface: "lab_asap7" as const };
  const report = proxy.report;
  const resultsDir = typeof report.results_dir === "string" ? report.results_dir : "";
  if (!/^tools\/OpenROAD-flow-scripts\/flow\/results\/asap7\/[^/]+\/lab_asap7_[^/]+$/.test(resultsDir)) {
    return { runs: [], surface: "lab_asap7" as const };
  }
  const reportPath = `sim/reports/${proxy.name}`;
  return {
    surface: "lab_asap7" as const,
    runs: [
      {
        runId: report.run_id,
        run_id: report.run_id,
        surface: "lab_asap7",
        variant: report.variant,
        design: report.design ?? null,
        pdk: "asap7",
        track: report.track,
        status: report.status,
        ok: report.ok === true,
        productWin: false,
        product_win: false,
        win_eligible: false,
        comparable_to_gold_ir: false,
        reportPaths: [reportPath],
        resultsDir,
        mesh_id: report.mesh_id,
        mesh_fingerprint: report.mesh_fingerprint,
        topology: report.topology,
        oracle: report.oracle,
        honesty: report.honesty,
        honesty_reason: report.honesty_reason,
        tool_id: report.tool_id,
        license_class: report.license_class,
        lab_admit: report.lab_admit,
        pillars: report.pillars,
      },
    ],
  };
}

function evidenceForUi(evidence: LabPillarEvidence) {
  return {
    status: evidence.status,
    honesty: evidence.honesty,
    honestyReason: evidence.honestyReason,
    leftovers: evidence.leftovers,
    toolId: evidence.toolId,
    licenseClass: evidence.licenseClass,
    modelId: evidence.modelId,
    powermapKind: evidence.powermapKind,
  };
}

function readAsap7Lab(): Record<string, unknown> | null {
  const raw = readJson("sim/reports/lab_asap7.json");
  const folio = readAsap7Folio();
  const proxy = readAsap7ProxyReport();
  const proxyReport = proxy?.report ?? null;
  const lvs = readJson("sim/reports/lab_asap7_lvs.json");
  const mmmc = readJson("sim/reports/lab_asap7_mmmc.json");
  const drc = readJson("sim/reports/lab_asap7_drc.json");
  const thermal = readJson("sim/reports/lab_asap7_thermal.json");
  const folioBlob = readJson("sim/reports/lab_asap7_folio.json");
  const pdk = readJson("sim/reports/lab_asap7_pdk.json");
  const spice = readJson("sim/reports/lab_asap7_spice.json");
  const pkg = readJson("sim/reports/lab_asap7_pkg.json");
  const chipPdn = readJson("sim/reports/lab_asap7_chip_pdn.json");
  if (!raw && !folio.length && !proxyReport && !thermal && !chipPdn) return null;
  const irReport = proxyReport ?? raw ?? chipPdn;
  const qor = asap7QorOf(proxyReport) ?? asap7QorOf(raw);
  const irPillar = labPillarOf(irReport, "ir");
  const thermalPillar = thermal
    ? labPillarOf(thermal, "thermal", true)
    : labPillarOf(proxyReport, "thermal");
  const admissionInput = proxyReport
    ? thermal
      ? { ...proxyReport, thermal_report: thermal }
      : proxyReport
    : null;
  const admission = evaluateLabAdmit(admissionInput);
  const leftovers = irPillar.leftovers;
  const pkgBump = (pkg?.bump as Record<string, unknown>) || {};
  const pkgRdl = (pkg?.rdl as Record<string, unknown>) || {};
  const pkgPdn = (pkg?.system_pdn as Record<string, unknown>) || {};
  const pkgBumpPkg = (pkgBump.package as Record<string, unknown>) || {};
  const spiceWave = (spice?.wave as Record<string, unknown>) || {};
  const setup = (mmmc?.setup as Record<string, unknown>) || {};
  const hold = (mmmc?.hold as Record<string, unknown>) || {};
  return {
    // The root status is the IR tool outcome; PROXY stays on the honesty axis.
    ok: irReport?.ok === true,
    status: irPillar.status,
    honesty: irPillar.honesty,
    honestyReason: irPillar.honestyReason,
    leftovers,
    variant: proxyReport?.variant ?? raw?.variant ?? null,
    design: proxyReport?.design ?? raw?.design ?? null,
    corner: proxyReport?.corner ?? raw?.corner ?? null,
    vt: proxyReport?.vt ?? raw?.vt ?? [],
    libModel: proxyReport?.lib_model ?? raw?.lib_model ?? null,
    track: proxyReport?.track ?? raw?.track ?? null,
    laneTrack: proxyReport?.lane_track ?? proxyReport?.lane ?? null,
    clkPs: n(proxyReport?.clk_ps ?? raw?.clk_ps),
    gds: raw?.gds ?? null,
    surface: raw?.surface ?? proxyReport?.surface ?? "lab",
    platform: raw?.platform ?? proxyReport?.platform ?? "asap7",
    meshId: proxyReport?.mesh_id ?? null,
    meshFingerprint: proxyReport?.mesh_fingerprint ?? null,
    oracle: proxyReport?.oracle ?? null,
    topology: proxyReport?.topology ?? null,
    scenario: proxyReport?.scenario ?? null,
    toolId: irPillar.toolId,
    licenseClass: irPillar.licenseClass,
    productWin: false,
    winEligible: false,
    comparableToGoldIr: false,
    labAdmit: admission.ok,
    labAdmitReason: admission.reason,
    proxyReportPath: proxy?.name ? `sim/reports/${proxy.name}` : null,
    pillars: {
      ir: evidenceForUi(irPillar),
      thermal: evidenceForUi(thermalPillar),
    },
    thermal: evidenceForUi(thermalPillar),
    leftover: raw?.leftover ?? null,
    stages: raw?.stages ?? null,
    stoppedAt: raw?.stopped_at ?? null,
    closureLadder: folioBlob?.closure_ladder ?? null,
    track6: folioBlob?.track6 ?? { status: "GAP" },
    qor,
    folio,
    cookCount: folio.length,
    closedCount: folio.filter((r) => r.timing_closed === true).length,
    lvs: lvs
      ? {
          matchPct: n(lvs.match_pct),
          nMatched: n(lvs.n_matched),
          nLogic: n(lvs.n_logic),
          calibre: lvs.calibre === true,
          closed: lvs.lvs_closed === true,
        }
      : null,
    mmmc: mmmc
      ? {
          setupWnsPs: n(setup.wns_ps),
          holdWnsPs: n(hold.wns_ps),
          ok: mmmc.ok === true,
        }
      : null,
    drc: drc
      ? {
          nItems: n(drc.n_items),
          calibre: drc.calibre === true,
          status: drc.status ?? null,
        }
      : null,
    pdk: pdk
      ? {
          ok: pdk.ok === true,
          nPm: n(pdk.n_pm),
          nModel: n(pdk.n_model),
          corners: Array.isArray(pdk.corners) ? pdk.corners : [],
          calibreReady: pdk.calibre_ready === true,
          calibrePlaceholder: pdk.calibre_placeholder === true,
          drm: pdk.drm === true,
          cdslib: pdk.cdslib === true,
        }
      : null,
    spice: spice
      ? {
          ok: spice.ok === true,
          patch: spice.patch ?? "current Xyce layer mapping unavailable",
          inverted: spiceWave.inverted === true,
          voutWhenVinHigh: n(spiceWave.vout_when_vin_high),
          voutWhenVinLow: n(spiceWave.vout_when_vin_low),
        }
      : null,
    pkg: pkg
      ? {
          ok: pkg.ok === true,
          status: typeof pkg.status === "string" ? pkg.status : null,
          c4: pkg.c4 === true,
          touchstone: pkg.touchstone === true,
          nBumps: n(pkgBumpPkg.n_bumps),
          rdlOk: pkgRdl.evidence_ok === true || pkgRdl.ok === true,
          wroteFinal: pkgRdl.wrote_final === true,
          vdd: n(pkgPdn.vdd),
          droopMv: n(pkgPdn.droop_mv),
          leftover: "dummy 4×4 bump · sidecar RDL · compact VRM · not C4",
        }
      : null,
    chipPdn: chipPdn
      ? {
          ok: chipPdn.ok === true,
          status: typeof chipPdn.status === "string" ? chipPdn.status : null,
          tier: chipPdn.tier ?? "chip_mesh",
          pdnsim6ReportMv: n(chipPdn.pdnsim_6_report_mv),
          meshStaticMv: n(chipPdn.mesh_static_mv),
          meshTransientMv: n(chipPdn.mesh_transient_droop_mv),
          nR: n(chipPdn.n_r),
          patched: (chipPdn.mesh_patch as Record<string, unknown> | undefined)?.patched === true,
          leftover: "tier B chip mesh · not tier C package mesh",
        }
      : null,
    note:
      proxyReport?.note ??
      raw?.note ??
      "Live ASAP7 folio. Predictive FinFET. Not a product win.",
  };
}

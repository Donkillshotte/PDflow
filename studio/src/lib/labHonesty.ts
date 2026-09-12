/**
 * Lab-only evidence contract for ASAP7/BSPDN.
 *
 * `status` is the outcome of the tool or gate. `honesty` is the claim class
 * attached to that outcome. They are deliberately separate: PROXY is never a
 * status, and thermal coverage never inherits IR honesty.
 */

export const LAB_TOOL_STATUSES = ["pass", "fail", "blocked", "not_run"] as const;
export type LabToolStatus = (typeof LAB_TOOL_STATUSES)[number];

export const LAB_HONESTY_CLASSES = ["GAP", "PROXY", "PARTIAL"] as const;
export type LabHonesty = (typeof LAB_HONESTY_CLASSES)[number];

export type LabLeftover = {
  id: string;
  message: string;
  count?: number | null;
};

export type LabPillarId = "ir" | "thermal";

export type LabPillarEvidence = {
  status: LabToolStatus;
  honesty: LabHonesty;
  honestyReason: string | null;
  leftovers: LabLeftover[];
  toolId: string | null;
  licenseClass: string | null;
  modelId: string | null;
  powermapKind: "uniform" | "workload" | null;
};

export type LabMeshIdentity = {
  meshId?: string | null;
  meshFingerprint?: string | null;
  platform?: string | null;
  design?: string | null;
  nickname?: string | null;
  topology?: string | null;
  surface?: string | null;
};

export type LabAdmitEvaluation = {
  ok: boolean;
  reason: string;
  ir: LabPillarEvidence;
  thermal: LabPillarEvidence;
  meshId: string | null;
  schemaOk: boolean;
  thermalGapAllowed: boolean;
};

const PROXY_MESH_RE = /^asap7_bspdn_proxy_[a-z0-9][a-z0-9_.+-]*$/;
const ASAP7_MESH_RE = /^asap7_[a-z0-9][a-z0-9_.+-]*$/;
const NANGATE_MESH_RE = /^nangate_[a-z0-9][a-z0-9_.+-]*$/;
const CANDIDATE_MESH_RE = /^asap7_(?:candidate|bpr|bspdn)(?:_|$)/;
const FORBIDDEN_CHIP_MESH_RE = /^asap7_(?:bpr|bspdn)_chip$/;

function recordOf(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringOf(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return text ? text : null;
}

function positiveCount(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
    const count = Number(value);
    return count > 0 ? count : null;
  }
  return null;
}

function normalizeStatusValue(value: unknown): LabToolStatus | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim().toLowerCase().replace(/[- ]/g, "_");
  if (normalized === "pass" || normalized === "passed" || normalized === "ok") return "pass";
  if (normalized === "fail" || normalized === "failed" || normalized === "error") return "fail";
  if (normalized === "blocked" || normalized === "refused") return "blocked";
  if (normalized === "not_run" || normalized === "notrun" || normalized === "missing") return "not_run";
  // Legacy report vocabulary is normalized into the status axis. The claim
  // class remains independently GAP/PROXY and is never emitted as a status.
  if (normalized === "gap" || normalized === "proxy" || normalized === "partial") return "blocked";
  return null;
}

function ranFrom(report: Record<string, unknown> | null): boolean {
  if (!report) return false;
  const execution = String(report.execution_status ?? report.executionStatus ?? "").toUpperCase();
  if (["COMPLETED", "DONE", "RAN", "FINISHED"].includes(execution)) return true;
  if (report.ran === true || report.executed === true || report.engine_ran === true) return true;
  return typeof report.ok === "boolean";
}

/** Normalize the tool/gate outcome. This function never returns PROXY. */
export function labStatusOf(
  report: Record<string, unknown> | null,
  fallback: LabToolStatus = "not_run",
): LabToolStatus {
  if (!report) return fallback;
  const explicit = normalizeStatusValue(report.status);
  if (explicit) return explicit;
  if (ranFrom(report)) return report.ok === true ? "pass" : "fail";
  return fallback;
}

function normalizeHonestyValue(value: unknown): LabHonesty | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim().toUpperCase();
  return LAB_HONESTY_CLASSES.includes(normalized as LabHonesty)
    ? (normalized as LabHonesty)
    : null;
}

export function isAsap7BspdnProxyMesh(meshId: unknown): boolean {
  return typeof meshId === "string" && PROXY_MESH_RE.test(meshId.trim());
}

export function isAsap7Mesh(meshId: unknown): boolean {
  return typeof meshId === "string" && ASAP7_MESH_RE.test(meshId.trim());
}

export function isNangateMesh(meshId: unknown): boolean {
  return typeof meshId === "string" && NANGATE_MESH_RE.test(meshId.trim());
}

export function isAsap7CandidateMesh(meshId: unknown): boolean {
  return typeof meshId === "string" && CANDIDATE_MESH_RE.test(meshId.trim());
}

function meshIdOf(report: Record<string, unknown> | null): string | null {
  if (!report) return null;
  const ir = recordOf(report.ir);
  const pillars = recordOf(report.pillars);
  const irPillar = recordOf(pillars?.ir);
  return (
    stringOf(report.mesh_id) ??
    stringOf(report.meshId) ??
    stringOf(ir?.mesh_id) ??
    stringOf(irPillar?.mesh_id) ??
    null
  );
}

function normalizeLeftoverItem(value: unknown, fallbackId: string): LabLeftover | null {
  if (typeof value === "string") {
    const message = value.trim();
    return message ? { id: fallbackId, message } : null;
  }
  const item = recordOf(value);
  if (!item) return null;
  const message = stringOf(item.message) ?? stringOf(item.reason) ?? stringOf(item.detail);
  const id = stringOf(item.id) ?? stringOf(item.name) ?? fallbackId;
  if (!message) return null;
  return { id, message, count: positiveCount(item.count) };
}

/** Convert both the new array form and the legacy named leftover object. */
export function labLeftoversOf(report: Record<string, unknown> | null): LabLeftover[] {
  if (!report) return [];
  const source = report.leftovers ?? report.leftover;
  const rows: LabLeftover[] = [];
  if (Array.isArray(source)) {
    source.forEach((value, index) => {
      const item = normalizeLeftoverItem(value, `leftover_${index + 1}`);
      if (item) rows.push(item);
    });
  } else if (typeof source === "string") {
    const item = normalizeLeftoverItem(source, "leftover");
    if (item) rows.push(item);
  } else {
    const object = recordOf(source);
    if (object) {
      const directItem = normalizeLeftoverItem(object, "leftover");
      if (directItem && (object.id !== undefined || object.name !== undefined)) {
        rows.push(directItem);
      }
      const nested = Array.isArray(object.items) ? object.items : null;
      nested?.forEach((value, index) => {
        const item = normalizeLeftoverItem(value, `leftover_${index + 1}`);
        if (item) rows.push(item);
      });
      for (const [id, value] of Object.entries(object)) {
        if (
          id === "items" ||
          id === "id" ||
          id === "name" ||
          id === "message" ||
          id === "reason" ||
          id === "detail" ||
          id === "count" ||
          value == null ||
          value === false ||
          value === ""
        ) continue;
        const item = normalizeLeftoverItem(value, id);
        if (item) rows.push(item);
        else if (typeof value === "number" && value > 0) rows.push({ id, message: `${id}: ${value}` });
      }
    }
  }
  const reason = stringOf(report.honesty_reason) ?? stringOf(report.honestyReason);
  if (reason && !rows.some((row) => row.message === reason)) {
    rows.push({ id: "honesty", message: reason });
  }
  return rows.filter(
    (row, index, all) => all.findIndex((candidate) => candidate.id === row.id && candidate.message === row.message) === index,
  );
}

function honestyReasonOf(
  report: Record<string, unknown> | null,
  pillar: Record<string, unknown> | null,
  pillarId: LabPillarId,
): string | null {
  return (
    stringOf(pillar?.honesty_reason) ??
    stringOf(pillar?.honestyReason) ??
    stringOf(pillar?.reason) ??
    (pillarId === "ir" ? stringOf(report?.honesty_reason) ?? stringOf(report?.honestyReason) : null) ??
    null
  );
}

function honestyOf(
  report: Record<string, unknown> | null,
  pillarId: LabPillarId,
  pillar: Record<string, unknown> | null,
  meshId: string | null,
  standalone: boolean,
): LabHonesty {
  // Thermal is intentionally isolated. A root IR honesty label cannot make
  // an unrun thermal model look more complete.
  const explicit = normalizeHonestyValue(pillar?.honesty);
  if (explicit) return explicit;
  if (pillarId === "ir") {
    const root = normalizeHonestyValue(report?.honesty);
    if (root) return root;
    if (isAsap7BspdnProxyMesh(meshId)) return "PROXY";
  }
  if (pillarId === "thermal" && standalone) {
    return normalizeHonestyValue(report?.honesty) ?? "GAP";
  }
  return "GAP";
}

function toolIdOf(
  report: Record<string, unknown> | null,
  pillar: Record<string, unknown> | null,
): string | null {
  return stringOf(pillar?.tool_id) ?? stringOf(pillar?.toolId) ?? stringOf(report?.tool_id) ?? stringOf(report?.toolId);
}

function licenseClassOf(
  report: Record<string, unknown> | null,
  pillar: Record<string, unknown> | null,
): string | null {
  return stringOf(pillar?.license_class) ?? stringOf(pillar?.licenseClass) ?? stringOf(report?.license_class) ?? stringOf(report?.licenseClass);
}

function modelIdOf(
  report: Record<string, unknown> | null,
  pillar: Record<string, unknown> | null,
): string | null {
  return stringOf(pillar?.model_id) ?? stringOf(pillar?.modelId) ?? stringOf(report?.model_id) ?? stringOf(report?.modelId);
}

function powermapKindOf(
  report: Record<string, unknown> | null,
  pillar: Record<string, unknown> | null,
): "uniform" | "workload" | null {
  const value = stringOf(pillar?.powermap_kind) ?? stringOf(pillar?.powermapKind) ?? stringOf(report?.powermap_kind) ?? stringOf(report?.powermapKind);
  return value === "uniform" || value === "workload" ? value : null;
}

/** Read one pillar without ever borrowing honesty from another pillar. */
export function labPillarOf(
  report: Record<string, unknown> | null,
  pillarId: LabPillarId,
  standalone = false,
): LabPillarEvidence {
  const pillars = recordOf(report?.pillars);
  const pillar = recordOf(pillars?.[pillarId]);
  const meshId = meshIdOf(report);
  const source =
    pillar ??
    (pillarId === "ir"
      ? report
      : recordOf(report?.thermal_report) ?? recordOf(report?.thermal) ?? (standalone ? report : null));
  const effectivePillar = pillar ?? (pillarId === "thermal" ? source : null);
  const status = labStatusOf(
    source,
    source && pillarId === "ir" && source !== report ? labStatusOf(report) : "not_run",
  );
  const leftovers = (source ? labLeftoversOf(source) : []).concat(
    pillarId === "ir" && source !== report ? labLeftoversOf(report) : [],
  ).filter(
    (row, index, all) => all.findIndex((candidate) => candidate.id === row.id && candidate.message === row.message) === index,
  );
  return {
    status,
    honesty: honestyOf(report, pillarId, effectivePillar, meshId, standalone),
    honestyReason: honestyReasonOf(report, effectivePillar, pillarId),
    leftovers,
    toolId: toolIdOf(report, source),
    licenseClass: licenseClassOf(report, source),
    modelId: modelIdOf(report, source),
    powermapKind: powermapKindOf(report, source),
  };
}

function identityOf(value: LabMeshIdentity | Record<string, unknown> | null | undefined): LabMeshIdentity {
  const row = (value ?? {}) as Record<string, unknown>;
  return {
    meshId: stringOf(row.meshId) ?? stringOf(row.mesh_id),
    meshFingerprint: stringOf(row.meshFingerprint) ?? stringOf(row.mesh_fingerprint),
    platform: stringOf(row.platform),
    design: stringOf(row.design),
    nickname: stringOf(row.nickname) ?? stringOf(row.nick),
    topology: stringOf(row.topology),
    surface: stringOf(row.surface),
  };
}

/**
 * Same-mesh comparisons are strict by construction. Missing fingerprints are
 * never treated as equal, even when the mesh id happens to match.
 */
export function isSameMeshCompatible(
  left: LabMeshIdentity | Record<string, unknown> | null | undefined,
  right: LabMeshIdentity | Record<string, unknown> | null | undefined,
): boolean {
  const a = identityOf(left);
  const b = identityOf(right);
  if (!a.meshId || !b.meshId || !a.meshFingerprint || !b.meshFingerprint) return false;
  if (FORBIDDEN_CHIP_MESH_RE.test(a.meshId) || FORBIDDEN_CHIP_MESH_RE.test(b.meshId)) return false;
  if (a.meshId !== b.meshId || a.meshFingerprint !== b.meshFingerprint) return false;
  if (a.platform !== "asap7" || b.platform !== "asap7") return false;
  if (!a.design || !b.design || a.design !== b.design) return false;
  const aNick = a.nickname ?? a.design;
  const bNick = b.nickname ?? b.design;
  if (aNick !== bNick) return false;
  if (a.topology && b.topology && a.topology !== b.topology) return false;
  return true;
}

/** Relative comparison firewall used by the lab, never by Product scoring. */
export function isLabComparisonCompatible(
  left: LabMeshIdentity | Record<string, unknown> | null | undefined,
  right: LabMeshIdentity | Record<string, unknown> | null | undefined,
  sameMesh = false,
): boolean {
  const a = identityOf(left);
  const b = identityOf(right);
  if (!a.meshId || !b.meshId) return false;
  if (FORBIDDEN_CHIP_MESH_RE.test(a.meshId) || FORBIDDEN_CHIP_MESH_RE.test(b.meshId)) return false;
  if (isNangateMesh(a.meshId) || isNangateMesh(b.meshId)) return false;
  if (!isAsap7Mesh(a.meshId) || !isAsap7Mesh(b.meshId)) return false;
  if (a.topology && b.topology && a.topology !== b.topology) return false;
  if (isAsap7CandidateMesh(a.meshId) !== isAsap7CandidateMesh(b.meshId)) return false;
  return sameMesh ? isSameMeshCompatible(a, b) : a.platform === "asap7" && b.platform === "asap7";
}

function schemaPass(report: Record<string, unknown>): boolean {
  const schema = recordOf(report.schema);
  const direct = [report.schema_ok, report.schema_valid, report.firewall_ok, report.contract_ok]
    .find((value) => typeof value === "boolean");
  if (typeof direct === "boolean") return direct;
  if (schema?.ok === true || schema?.valid === true) return true;
  const stampedAdmission = recordOf(report.lab_admit);
  return (
    stampedAdmission?.ok === true &&
    report.ok_claim === false &&
    report.product_signoff === false &&
    report.product_win === false &&
    report.comparable_to_gold_ir === false
  );
}

function forbiddenProductClaim(report: Record<string, unknown>): string | null {
  const claims: [string, unknown][] = [
    ["product_win", report.product_win],
    ["productWin", report.productWin],
    ["win_eligible", report.win_eligible],
    ["winEligible", report.winEligible],
    ["comparable_to_gold_ir", report.comparable_to_gold_ir],
    ["comparableToGoldIr", report.comparableToGoldIr],
  ];
  const hit = claims.find(([, value]) => value === true);
  return hit ? `forbidden Product claim ${hit[0]}=true` : null;
}

/**
 * Evaluate the lab-only proxy-first admission. Thermal GAP/not_run is
 * explicitly admissible when it is the only missing claim class.
 */
export function evaluateLabAdmit(report: Record<string, unknown> | null): LabAdmitEvaluation {
  const ir = labPillarOf(report, "ir");
  const thermalReport = recordOf(report?.thermal_report) ?? recordOf(report?.thermal);
  const thermal = thermalReport
    ? labPillarOf(thermalReport, "thermal", true)
    : labPillarOf(report, "thermal");
  const meshId = meshIdOf(report);
  const schemaOk = report ? schemaPass(report) : false;
  const thermalGapAllowed =
    thermal.honesty === "GAP" && (thermal.status === "not_run" || thermal.status === "blocked");

  if (!report) return { ok: false, reason: "proxy report missing", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  if (report.surface !== "lab" && report.surface !== "lab_asap7") {
    return { ok: false, reason: "surface is not lab", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (report.platform !== "asap7") {
    return { ok: false, reason: "platform is not asap7", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (report.track === "asap7_bb") {
    return { ok: false, reason: "ASAP7-BB is citation/EDU only", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  const claim = forbiddenProductClaim(report);
  if (claim) return { ok: false, reason: claim, ir, thermal, meshId, schemaOk, thermalGapAllowed };
  if (!isAsap7BspdnProxyMesh(meshId)) {
    return { ok: false, reason: "proxy BSPDN mesh id missing", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (!schemaOk) {
    return { ok: false, reason: "lab schema/firewall has not passed", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (ir.status !== "pass") {
    return { ok: false, reason: `IR tool status is ${ir.status}`, ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (ir.honesty !== "PROXY" && ir.honesty !== "PARTIAL") {
    return { ok: false, reason: `IR honesty is ${ir.honesty}`, ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (ir.honesty === "PROXY" && (!ir.toolId || !ir.licenseClass)) {
    return { ok: false, reason: "PROXY IR row requires tool_id and license_class", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (ir.honesty === "PROXY" && !ir.honestyReason && ir.leftovers.length === 0) {
    return { ok: false, reason: "PROXY IR row requires a leftover or honesty_reason", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (thermal.honesty !== "GAP" && thermal.honesty !== "PROXY") {
    return { ok: false, reason: "thermal pillar must be GAP or a declared PROXY", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (thermal.honesty === "PROXY" && (!thermal.modelId || !thermal.powermapKind)) {
    return { ok: false, reason: "thermal PROXY requires model_id and powermap_kind", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  if (thermal.status === "fail" && !thermalGapAllowed) {
    return { ok: false, reason: "thermal tool failed", ir, thermal, meshId, schemaOk, thermalGapAllowed };
  }
  return {
    ok: true,
    reason: thermalGapAllowed
      ? "IR PROXY-first admitted; thermal GAP is explicit and not the sole blocker"
      : "IR PROXY-first admitted with separate thermal evidence",
    ir,
    thermal,
    meshId,
    schemaOk,
    thermalGapAllowed,
  };
}

// Keep these helpers easy to discover from signoff-oriented callers.
export const sameMeshCompatible = isSameMeshCompatible;
export const labComparisonCompatible = isLabComparisonCompatible;

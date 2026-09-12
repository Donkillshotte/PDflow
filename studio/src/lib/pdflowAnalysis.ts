import fs from "fs";
import crypto from "crypto";
import path from "path";
import { agentFetch } from "./agentClient";
import { LEARN_ROOT } from "./course";
import { preferredResultsVariant } from "./open";
import { isCurrentReport } from "./liveReports";
import type {
  PackageEvidence,
  PackageManifest,
  PathLedger,
  ReportStatus,
} from "./pdflowContracts";
import { fallbackContext } from "./pdflowContext";

const LAB_REPORT_FILES: Record<string, string> = {
  pkg_bump: "lab_asap7_pkg_bump.json",
  pkg_rdl: "lab_asap7_pkg_rdl.json",
  pkg_signoff: "lab_asap7_pkg.json",
  system_pdn: "lab_asap7_system_pdn.json",
  thermal_signoff: "lab_asap7_thermal.json",
};

function reportFilename(name: string, variant: string): string {
  return variant.startsWith("lab_asap7_")
    ? LAB_REPORT_FILES[name] || name + "_" + variant + ".json"
    : name + "_" + variant + ".json";
}

function readLive(name: string, variant: string): Record<string, unknown> | null {
  const file = path.join(
    LEARN_ROOT,
    "sim",
    "reports",
    reportFilename(name, variant),
  );
  if (!isCurrentReport(file, variant)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function reportStatus(
  report: Record<string, unknown> | null,
  missingStatus: ReportStatus = "NOT_RUN",
): ReportStatus {
  if (!report) return missingStatus;
  const raw = String(report.status || "").toUpperCase() as ReportStatus;
  if (
    ["PASS", "FAIL", "WARN", "PARTIAL", "PROXY", "GAP", "NOT_RUN"].includes(raw)
  ) {
    return raw;
  }
  return report.ok === true ? "PASS" : report.ok === false ? "FAIL" : "NOT_RUN";
}

function fallbackPackage(variantOverride?: string): PackageEvidence {
  const variant = variantOverride || preferredResultsVariant();
  const system = readLive("system_pdn", variant);
  const bump = readLive("pkg_bump", variant);
  const rdl = readLive("pkg_rdl", variant);
  const pkg = readLive("pkg_signoff", variant);
  const manifest = readLive("pkg_manifest", variant);
  const thermal = readLive("thermal_signoff", variant);
  const systemStatus = reportStatus(system, "GAP");
  const pkgStatus = reportStatus(pkg);
  const rdlStatus = reportStatus(rdl);
  const manifestStatus = reportStatus(manifest);
  const manifestRdl = (manifest?.rdl || {}) as Record<string, unknown>;
  const manifestEvidenceOk = manifest?.evidence_ok === true;
  const rdlEvidenceOk =
    rdl?.evidence_ok === true ||
    (manifestRdl.ready === true &&
      Array.isArray(manifestRdl.missing_nets) &&
      manifestRdl.missing_nets.length === 0);
  const overall: ReportStatus =
    systemStatus === "GAP" || systemStatus === "NOT_RUN"
      ? "GAP"
      : manifestStatus === "GAP" || manifestStatus === "NOT_RUN"
        ? manifest
          ? manifestStatus
          : pkgStatus === "FAIL"
            ? "FAIL"
            : pkgStatus === "PROXY"
              ? "PROXY"
              : pkg?.ok === true && rdlStatus === "PASS"
                ? "PROXY"
                : "PARTIAL"
        : manifestStatus === "FAIL"
          ? "FAIL"
          : manifestStatus === "PROXY"
            ? "PROXY"
            : pkgStatus === "FAIL"
          ? "FAIL"
          : pkgStatus === "PROXY"
            ? "PROXY"
            : pkg?.ok === true && rdlStatus === "PASS"
              ? "PROXY"
              : "PARTIAL";
  const systemTransient = (system?.transient || {}) as Record<string, unknown>;
  const systemImpedance = (system?.impedance || {}) as Record<string, unknown>;
  // Preserve the requested variant even when the desktop agent is stale or
  // unavailable.  Mixing a selected 480ps package report with the preferred
  // 320ps finish snapshot would make the evidence envelope internally false.
  const context = fallbackContext("package", variant);
  const computedInputFingerprint = crypto
    .createHash("sha256")
    .update(
      context.finish
        .slice()
        .sort((left, right) =>
          left.relative_path.localeCompare(right.relative_path),
        )
        .map((item) => item.content_hash || "")
        .join("\n"),
    )
    .digest("hex");
  const manifestProvenance = (manifest?.provenance || {}) as Record<string, unknown>;
  const inputFingerprint =
    typeof manifestProvenance.input_fingerprint === "string"
      ? manifestProvenance.input_fingerprint
      : computedInputFingerprint;
  return {
    schema_version: 1,
    scope: "package",
    variant,
    status: overall,
    ok: false,
    evidence_ok: manifestEvidenceOk,
    comparison_scope: "same-live-invocation",
    oracle: "current-finish-snapshot",
    input_artifacts: context.finish,
    input_fingerprint: inputFingerprint,
    manifest: manifest as PackageManifest | null,
    steps: {
      pkg_bump: {
        status: reportStatus(bump),
        ok: bump?.ok === true,
        summary: typeof bump?.summary === "string" ? bump.summary : undefined,
        report: "learn/sim/reports/" + reportFilename("pkg_bump", variant),
      },
      pkg_rdl: {
        status: rdlStatus,
        ok: rdlEvidenceOk,
        evidence_ok: rdlEvidenceOk,
        summary: typeof rdl?.summary === "string" ? rdl.summary : undefined,
        report: "learn/sim/reports/" + reportFilename("pkg_rdl", variant),
        educational: true,
      },
      package_manifest: {
        status: manifestStatus,
        ok: manifestEvidenceOk,
        evidence_ok: manifestEvidenceOk,
        summary:
          typeof manifest?.summary === "string" ? manifest.summary : undefined,
        report: "learn/sim/reports/pkg_manifest_" + variant + ".json",
        manifest: true,
      },
      system_pdn: {
        status: systemStatus,
        ok: system?.ok === true,
        summary: typeof system?.summary === "string" ? system.summary : undefined,
        reason: typeof system?.reason === "string" ? system.reason : null,
        engine: typeof system?.engine === "string" ? system.engine : null,
        droop_mv:
          typeof systemTransient.droop_mv === "number"
            ? systemTransient.droop_mv
            : null,
        zmax_mohm:
          typeof systemImpedance.z_max_mohm === "number"
            ? systemImpedance.z_max_mohm
            : null,
        report: "learn/sim/reports/" + reportFilename("system_pdn", variant),
      },
      thermal_signoff: {
        status: reportStatus(thermal),
        ok: thermal?.ok === true,
        summary: typeof thermal?.summary === "string" ? thermal.summary : undefined,
        report:
          "learn/sim/reports/" + reportFilename("thermal_signoff", variant),
      },
    },
    product_signoff: {
      status: "NOT_RUN",
      reason: "Package evidence cannot close Product signoff",
    },
    generated_at: new Date().toISOString(),
  };
}

function fallbackPathLedger(variantOverride?: string): PathLedger {
  const variant = variantOverride || preferredResultsVariant();
  const sta = readLive("sta_signoff", variant);
  const staIr = readLive("sta_ir_aware", variant);
  const timing = (sta?.timing || {}) as Record<string, unknown>;
  const leftover = (sta?.leftover || {}) as Record<string, unknown>;
  const timingStatus: ReportStatus = !sta
    ? "GAP"
    : leftover.setup_open === true
      ? "FAIL"
      : "PASS";
  const irStatus = staIr?.ok === true ? "PASS" : "GAP";
  const ledgerStatus: ReportStatus =
    timingStatus === "GAP" || irStatus === "GAP"
      ? "GAP"
      : timingStatus === "FAIL"
        ? "FAIL"
        : "WARN";
  const context = fallbackContext("flow", variant);
  const meshId = crypto
    .createHash("sha256")
    .update(
      "variant=" +
        variant +
        "\n" +
        context.finish
          .slice()
          .sort((left, right) =>
            left.relative_path.localeCompare(right.relative_path),
          )
          .map((item) => item.content_hash || "")
          .join("\n"),
    )
    .digest("hex")
    .slice(0, 24);
  return {
    schema_version: 1,
    scope: "flow",
    variant,
    status: ledgerStatus,
    ok: false,
    mesh_id: meshId,
    oracle: "current-finish-snapshot",
    comparison_scope: "same-live-invocation",
    entries: [
      {
        id: "worst-timing-endpoint",
        endpoint: timing.worst_endpoint || null,
        status: timingStatus,
        wns_ns: timing.wns_ns ?? null,
        tns: timing.tns ?? null,
        setup_violations: timing.setup_violations ?? null,
        reason: leftover.note || null,
      },
      {
        id: "timing-ir-aware",
        endpoint: timing.worst_endpoint || null,
        status: staIr?.ok === true ? "PASS" : "GAP",
        slack_ns: staIr?.slack_ns ?? null,
        slack_ir_ns: staIr?.slack_ir_ns ?? null,
        n_joined: staIr?.n_joined ?? null,
      },
    ],
    meshes: [
      {
        id: "dynamic_ir",
        status: reportStatus(readLive("dynamic_ir", variant), "GAP"),
        comparison_scope: "same-live-invocation",
      },
      {
        id: "chip_pdn",
        status: reportStatus(readLive("pdn_chip_ir", variant), "GAP"),
        comparison_scope: "distinct-live-mesh",
      },
      {
        id: "system_pdn",
        status: reportStatus(readLive("system_pdn", variant), "GAP"),
        comparison_scope: "distinct-live-mesh",
      },
    ],
    note: "No historical report or different mesh is used as a baseline.",
    generated_at: new Date().toISOString(),
  };
}

export async function getPackageEvidence(
  variant?: string,
): Promise<PackageEvidence> {
  const selectedVariant = variant ?? preferredResultsVariant();
  const remote = await agentFetch<PackageEvidence>(
    "/v1/package?variant=" + encodeURIComponent(selectedVariant),
  );
  // The desktop agent can outlive a source update during development.  Do
  // not let an older response hide the manifest contract: the local fallback
  // reads the same current reports and enforces the selected variant/mtime.
  if (
    remote &&
    remote.manifest !== undefined &&
    typeof remote.evidence_ok === "boolean"
  ) {
    return remote;
  }
  return fallbackPackage(selectedVariant);
}

export async function getPathLedger(
  variant?: string,
): Promise<PathLedger> {
  const selectedVariant = variant ?? preferredResultsVariant();
  return (
    (await agentFetch<PathLedger>(
      "/v1/path-ledger?variant=" + encodeURIComponent(selectedVariant),
    )) || fallbackPathLedger(selectedVariant)
  );
}

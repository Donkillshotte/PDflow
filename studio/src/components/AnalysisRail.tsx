"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Info, Play, RefreshCw, XCircle } from "lucide-react";
import clsx from "clsx";
import type { CheckEligibility, CheckPolicy, EvidenceIndex, EvidenceRecord, ReportStatus } from "@/lib/pdflowContracts";

const STATUS_LABELS: Record<ReportStatus, string> = {
  PASS: "PASS",
  FAIL: "FAIL",
  WARN: "WARN",
  PARTIAL: "PARTIAL",
  PROXY: "PROXY",
  GAP: "GAP",
  NOT_RUN: "NOT RUN",
};

function statusIcon(status: ReportStatus) {
  if (status === "PASS") return CheckCircle2;
  if (status === "FAIL") return XCircle;
  if (status === "WARN" || status === "GAP") return AlertTriangle;
  return CircleDashed;
}

function statusClass(status: ReportStatus): string {
  return "analysis-status-" + status.toLowerCase();
}

function compactReason(check: CheckEligibility): string {
  if (check.missing.length) return check.missing[0];
  if (check.incompatible.length) return check.incompatible[0];
  if (check.report_reason) return check.report_reason;
  if (check.warnings.length) return check.warnings[0];
  return check.description;
}

function metricLabel(key: string): string {
  return key
    .replace(/_mv$/, " · mV")
    .replace(/_ns$/, " · ns")
    .replace(/_v$/, " · V")
    .replace(/_a$/, " · A")
    .replace(/_mohm$/, " · mΩ")
    .replaceAll("_", " ");
}

function metricValue(key: string, value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  return String(value ?? "—");
}

type KnobSchema = Record<string, unknown>;

function knobLabel(key: string): string {
  return key
    .replace(/_ns$/, "")
    .replace(/_ps$/, "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function knobValue(
  values: Record<string, unknown>,
  key: string,
  schema: KnobSchema,
): unknown {
  return values[key] ?? schema.default ?? "";
}

function collectKnobValues(
  values: Record<string, unknown>,
  schema: Record<string, KnobSchema> | undefined,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, definition] of Object.entries(schema ?? {})) {
    if (definition.supported === false) continue;
    const value = values[key] ?? definition.default;
    if (value === undefined || value === "") continue;
    if (definition.type === "number" || definition.type === "integer") {
      const number = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(number)) continue;
      result[key] = definition.type === "integer" ? Math.trunc(number) : number;
    } else if (definition.type === "boolean") {
      result[key] = Boolean(value);
    } else {
      result[key] = value;
    }
  }
  return result;
}

export function AnalysisRail({
  stage,
  variant,
  runId,
  refreshKey = 0,
  onRunAction,
}: {
  stage: string;
  variant: string;
  runId?: string | null;
  refreshKey?: number;
  onRunAction?: (
    action: string,
    check: CheckEligibility,
    parameters?: Record<string, unknown>,
  ) => void;
}) {
  const [policy, setPolicy] = useState<CheckPolicy | null>(null);
  const [evidence, setEvidence] = useState<EvidenceIndex | null>(null);
  const [parameters, setParameters] = useState<Record<string, Record<string, unknown>>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const query = new URLSearchParams({ stage, variant });
    if (runId) query.set("run_id", runId);
    fetch("/api/checks?" + query.toString(), {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { reason?: string } | null;
          throw new Error(body?.reason || "analysis policy unavailable");
        }
        return (await response.json()) as CheckPolicy;
      })
      .then((next) => setPolicy(next))
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        setPolicy(null);
        setError(cause instanceof Error ? cause.message : "analysis policy unavailable");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [refreshKey, runId, stage, variant]);

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ stage, variant });
    if (runId) query.set("run_id", runId);
    fetch("/api/evidence?" + query.toString(), {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) return null;
        return (await response.json()) as EvidenceIndex;
      })
      .then((next) => setEvidence(next))
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        setEvidence(null);
      });
    return () => controller.abort();
  }, [refreshKey, runId, stage, variant]);

  const checks = useMemo(
    () => {
      const scope = stage === "package" ? "package" : "flow";
      return (policy?.checks ?? []).filter((item) => item.scope === scope);
    },
    [policy, stage],
  );
  const available = checks.filter((item) => item.eligible).length;
  const blockers = checks.filter((item) => !item.eligible || item.status === "FAIL" || item.status === "GAP").length;
  const evidenceByCheck = useMemo(
    () => new Map((evidence?.evidence ?? []).map((item) => [item.check_id, item] as const)),
    [evidence],
  );

  useEffect(() => {
    setParameters((current) => {
      let changed = false;
      const next = { ...current };
      for (const check of checks) {
        const schema = check.knob_schema ?? {};
        const previous = current[check.check_id] ?? {};
        const values = { ...previous };
        for (const knob of check.knobs) {
          if (values[knob] !== undefined) continue;
          const defaultValue = schema[knob]?.default;
          if (defaultValue !== undefined) {
            values[knob] = defaultValue;
            changed = true;
          }
        }
        if (Object.keys(values).length > 0 && !current[check.check_id]) {
          changed = true;
        }
        next[check.check_id] = values;
      }
      return changed ? next : current;
    });
  }, [checks]);

  function updateParameter(
    checkId: string,
    key: string,
    definition: KnobSchema,
    rawValue: string | boolean,
  ) {
    let value: unknown = rawValue;
    if (definition.type === "number" || definition.type === "integer") {
      value = rawValue === "" ? "" : Number(rawValue);
    }
    setParameters((current) => ({
      ...current,
      [checkId]: { ...(current[checkId] ?? {}), [key]: value },
    }));
  }

  async function refresh() {
    setPolicy(null);
    setLoading(true);
    setError(null);
    const query = new URLSearchParams({ stage, variant });
    if (runId) query.set("run_id", runId);
    try {
      const response = await fetch("/api/checks?" + query.toString(), { cache: "no-store" });
      const next = (await response.json()) as CheckPolicy;
      if (!response.ok) throw new Error(next.reason || "analysis policy unavailable");
      setPolicy(next);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "analysis policy unavailable");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="analysis-rail" aria-label="Checkpoint analysis eligibility">
      <div className="analysis-rail-header">
        <div>
          <span className="workspace-panel-kicker">Checkpoint checks</span>
          <h3>{stage === "pdn" ? "Chip PDN" : stage}</h3>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Refresh checkpoint analysis"
          title="Refresh checkpoint analysis"
          onClick={() => void refresh()}
        >
          <RefreshCw size={14} aria-hidden />
        </button>
      </div>

      <div className="analysis-rail-summary" aria-live="polite">
        <span>{loading ? "Loading policy…" : available + " eligible"}</span>
        <span>{checks.length ? blockers + " require attention" : "No checks loaded"}</span>
      </div>

      {error && (
        <div className="analysis-rail-state analysis-rail-error" role="status">
          <AlertTriangle size={14} aria-hidden />
          <span>{error}</span>
        </div>
      )}

      {!error && !loading && checks.length === 0 && (
        <div className="analysis-rail-state">
          <Info size={14} aria-hidden />
          <span>No checkpoint policy is available yet.</span>
        </div>
      )}

      <div className="analysis-rail-list">
        {checks.map((check) => {
          const Icon = statusIcon(check.status);
          const runAction = onRunAction;
          const canRun = Boolean(check.eligible && check.action && runAction);
          const record = evidenceByCheck.get(check.check_id);
          return (
            <article key={check.check_id} className={clsx("analysis-check", !check.eligible && "is-disabled")}>
              <div className="analysis-check-heading">
                <Icon size={15} className={statusClass(check.status)} aria-hidden />
                <strong>{check.display_name}</strong>
                <span className={clsx("analysis-status", statusClass(check.status))}>
                  {STATUS_LABELS[check.status]}
                </span>
              </div>
              <div className="analysis-check-meta">
                <span>{check.evidence_class}</span>
                <span>{check.cost_class}</span>
                {check.stale && <span>STALE</span>}
                {check.estimated_duration_seconds && <span>~{check.estimated_duration_seconds}s</span>}
              </div>
              <div className="analysis-check-dimensions" aria-label={`${check.display_name} status dimensions`}>
                <span>exec {check.execution_status || "NOT_RUN"}</span>
                <span>evidence {check.evidence_status || "NOT_RUN"}</span>
                <span>req {check.requirement_status || check.status}</span>
                <span>signoff {check.signoff_status || "NOT_RUN"}</span>
              </div>
              {check.metrics && Object.keys(check.metrics).length > 0 && (
                <div className="analysis-check-metrics" aria-label={`${check.display_name} metrics`}>
                  {Object.entries(check.metrics).slice(0, 4).map(([key, value]) => (
                    <span key={key}>
                      <small>{metricLabel(key)}</small>
                      <strong>{metricValue(key, value)}</strong>
                    </span>
                  ))}
                </div>
              )}
              {check.knobs.length > 0 && (
                <details className="analysis-check-knobs">
                  <summary>Controls · {check.knobs.length}</summary>
                  <div className="analysis-check-knob-grid">
                    {check.knobs.map((knob) => {
                      const definition = check.knob_schema?.[knob] ?? { type: "string" };
                      const supported = definition.supported !== false;
                      const value = knobValue(parameters[check.check_id] ?? {}, knob, definition);
                      const type = String(definition.type ?? "string");
                      const options = Array.isArray(definition.options)
                        ? definition.options.map(String)
                        : [];
                      return (
                        <label
                          key={knob}
                          className={clsx("analysis-knob", !supported && "is-derived")}
                          title={
                            supported
                              ? "Adapter input for this analysis"
                              : "Derived or not exposed by the native adapter"
                          }
                        >
                          <span>
                            {knobLabel(knob)}
                            {definition.unit ? ` · ${String(definition.unit)}` : ""}
                          </span>
                          {type === "enum" ? (
                            <select
                              value={String(value ?? "")}
                              disabled={!supported}
                              onChange={(event) =>
                                updateParameter(check.check_id, knob, definition, event.target.value)
                              }
                            >
                              {options.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          ) : type === "boolean" ? (
                            <input
                              type="checkbox"
                              checked={Boolean(value)}
                              disabled={!supported}
                              onChange={(event) =>
                                updateParameter(check.check_id, knob, definition, event.target.checked)
                              }
                            />
                          ) : (
                            <input
                              type={type === "number" || type === "integer" ? "number" : "text"}
                              value={String(value ?? "")}
                              min={typeof definition.min === "number" ? definition.min : undefined}
                              max={typeof definition.max === "number" ? definition.max : undefined}
                              step={
                                typeof definition.step === "number" || typeof definition.step === "string"
                                  ? definition.step
                                  : type === "integer"
                                    ? 1
                                    : undefined
                              }
                              disabled={!supported}
                              onChange={(event) =>
                                updateParameter(check.check_id, knob, definition, event.target.value)
                              }
                            />
                          )}
                          {!supported && <small>derived</small>}
                        </label>
                      );
                    })}
                  </div>
                </details>
              )}
              {record && <EvidenceDetails record={record} />}
              <p>{compactReason(check)}</p>
              <div className="analysis-check-footer">
                {check.action ? (
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    disabled={!canRun}
                    title={
                      !check.eligible
                        ? compactReason(check)
                      : runAction
                          ? "Run " + check.display_name
                          : "Use the operation runner to launch this check"
                    }
                    onClick={() => {
                      if (canRun && check.action && runAction) {
                        runAction(
                          check.action,
                          check,
                          collectKnobValues(parameters[check.check_id] ?? {}, check.knob_schema),
                        );
                      }
                    }}
                  >
                    <Play size={12} aria-hidden />
                    {check.status === "NOT_RUN" || check.stale ? "Run" : "Re-run"}
                  </button>
                ) : (
                  <span className="analysis-no-action">Stage report / capability state</span>
                )}
                {check.missing.length > 0 && <span className="analysis-missing">Prerequisite missing</span>}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function EvidenceDetails({ record }: { record: EvidenceRecord }) {
  const toolVersion = Object.entries(record.tool_versions ?? {})
    .map(([tool, version]) => `${tool} ${version || "unknown"}`)
    .join(" · ");
  return (
    <details className="analysis-check-evidence">
      <summary>Evidence details · {record.evidence_status}</summary>
      <dl>
        <div><dt>Tool</dt><dd>{toolVersion || "—"}</dd></div>
        <div><dt>Checkpoint</dt><dd title={record.checkpoint_id || undefined}>{record.checkpoint_id || "—"}</dd></div>
        <div><dt>Config</dt><dd title={record.configuration_hash || undefined}>{record.configuration_hash?.slice(0, 12) || "—"}</dd></div>
        <div><dt>Inputs</dt><dd>{record.input_artifact_hashes.length || "—"} verified hash{record.input_artifact_hashes.length === 1 ? "" : "es"}</dd></div>
        {record.report_paths.map((path) => <div key={path}><dt>Report</dt><dd title={path}>{path.split("/").pop()}</dd></div>)}
      </dl>
      {record.limitations.length > 0 && <p className="analysis-evidence-limitations">{record.limitations.join(" · ")}</p>}
    </details>
  );
}

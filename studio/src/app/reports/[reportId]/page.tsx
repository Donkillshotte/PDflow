"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import clsx from "clsx";

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

function isRecord(value: JsonValue | undefined): value is { [key: string]: JsonValue } {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function pretty(value: JsonValue | undefined): string {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

export default function ReportPage() {
  const params = useParams<{ reportId: string }>();
  const reportId = params.reportId;
  const [report, setReport] = useState<JsonValue | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setReport(null);
    setError(null);
    fetch("/api/reports/" + encodeURIComponent(reportId), { cache: "no-store" })
      .then(async (response) => {
        const body = (await response.json()) as JsonValue;
        if (!response.ok) {
          const reason = isRecord(body) && typeof body.reason === "string" ? body.reason : "Report unavailable (HTTP " + response.status + ")";
          throw new Error(reason);
        }
        return body;
      })
      .then((body) => {
        if (!cancelled) setReport(body);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Report unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  const data = isRecord(report) ? report : null;
  const status = typeof data?.status === "string" ? data.status : "NOT_RUN";
  const ok = data?.ok === true;
  const stale = data?.stale === true;

  return (
    <main className="report-page">
      <header className="page-head report-page-head">
        <div>
          <p className="eyebrow">Validated report</p>
          <h1>{reportId}</h1>
          <p>Structured provenance view for a report produced by the local agent.</p>
        </div>
        <Link href="/tools?tab=results" className="btn-ghost">Back to Tools</Link>
      </header>

      {error && <div className="report-state report-state-error" role="alert">{error}</div>}
      {!report && !error && <div className="report-state">Loading report…</div>}
      {data && (
        <>
          <section className="report-summary-grid" aria-label="Report summary">
            <div className={clsx("report-status-card", ok && "is-pass", stale && "is-stale")}>
              <span>Status</span>
              <strong>{status}</strong>
              <small>{stale ? "STALE · inputs changed or report is not current" : ok ? "Validated report" : "Requires attention"}</small>
            </div>
            <div className="report-fact"><span>Run</span><strong>{pretty(data.run_id)}</strong></div>
            <div className="report-fact"><span>Tool</span><strong>{pretty(data.tool_id ?? data.producer)}</strong></div>
            <div className="report-fact"><span>Reason</span><strong>{pretty(data.reason)}</strong></div>
          </section>

          <section className="report-detail-grid">
            <article className="panel report-detail-card">
              <h2>Provenance</h2>
              <dl>
                <div><dt>Report ID</dt><dd><code>{pretty(data.report_id ?? reportId)}</code></dd></div>
                <div><dt>Input artifacts</dt><dd><code>{pretty(data.input_artifacts ?? data.input_hashes)}</code></dd></div>
                <div><dt>Artifact</dt><dd><code>{pretty(data.artifact ?? data.artifact_id)}</code></dd></div>
                <div><dt>Comparison scope</dt><dd>{pretty(data.comparison_scope)}</dd></div>
                <div><dt>Generated</dt><dd>{pretty(data.generated_at ?? data.created_at)}</dd></div>
              </dl>
            </article>
            <article className="panel report-detail-card">
              <h2>Result</h2>
              <pre>{pretty(data.details ?? data.metrics ?? data.result)}</pre>
            </article>
          </section>

          <details className="report-raw">
            <summary>Show raw JSON</summary>
            <pre>{JSON.stringify(report, null, 2)}</pre>
          </details>
        </>
      )}
    </main>
  );
}

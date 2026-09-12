"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Activity, Box, Clock, Layers } from "lucide-react";

type Metric = {
  label: string;
  value: string;
  source: string;
};

type Digest = {
  errors: number;
  warnings: number;
  noiseWarnings: number;
  healthy: boolean;
  summary: string;
};

export function FlowLabMetricsBar({
  stage,
  variant,
  refreshKey,
  visible,
  runId,
}: {
  stage: string;
  variant: string;
  refreshKey: number;
  visible: boolean;
  runId?: string | null;
}) {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(false);
  const [wns, setWns] = useState<string | null>(null);
  const [digest, setDigest] = useState<Digest | null>(null);

  const load = useCallback(async () => {
    if (!visible || stage === "rtl") return;
    setLoading(true);
    const runQuery = runId ? `&run_id=${encodeURIComponent(runId)}` : "";
    try {
      const [resR, resI] = await Promise.all([
        fetch(
          `/api/results?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}${runQuery}`,
        ),
        fetch(
          `/api/inspections?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}${runQuery}`,
        ),
      ]);
      if (resR.ok) {
        const data = await resR.json();
        setMetrics((data.metrics ?? []).slice(0, 4));
        setDigest(data.logDigest ?? null);
      }
      if (resI.ok) {
        const body = (await resI.json()) as {
          inspection?: { sta?: { wns?: string | null } } | null;
        };
        const insp = body.inspection;
        setWns(insp?.sta?.wns ?? null);
      } else {
        setWns(null);
      }
    } catch {
      setMetrics([]);
      setDigest(null);
    } finally {
      setLoading(false);
    }
  }, [runId, stage, variant, visible]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  if (!visible || stage === "rtl") return null;

  return (
    <div className="fl-metrics" aria-busy={loading}>
      <div className="fl-metric-card">
        <Layers size={16} aria-hidden />
        <div>
          <span>Phase</span>
          <strong>{stage}</strong>
        </div>
      </div>
      {digest && (
        <div
          className={clsx(
            "fl-metric-card",
            digest.healthy ? "accent" : "warn-card",
          )}
          title={digest.summary}
        >
          <Activity size={16} aria-hidden />
          <div>
            <span>ORFS log</span>
            <strong>
              {digest.errors}E / {digest.warnings}W
              {digest.noiseWarnings > 0 ? ` · ${digest.noiseWarnings} noise` : ""}
            </strong>
          </div>
        </div>
      )}
      {wns && (
        <div className="fl-metric-card accent">
          <Clock size={16} aria-hidden />
          <div>
            <span>WNS</span>
            <strong className={clsx(wns.trim().startsWith("-") && "warn")}>
              {wns}
            </strong>
          </div>
        </div>
      )}
      {metrics.length === 0 && !loading && (
        <div className="fl-metric-card muted-card">
          <Box size={16} aria-hidden />
          <div>
            <span>Metrics</span>
            <strong>Run the phase</strong>
          </div>
        </div>
      )}
      {metrics.map((m, i) => {
        const scary = m.value.startsWith("-") || /violation count\s+[1-9]/i.test(m.value);
        return (
          <div key={`${m.source}-${m.label}-${i}`} className="fl-metric-card">
            <Activity size={16} aria-hidden />
            <div>
              <span>
                {m.label}
              </span>
              <strong className={clsx(scary && "warn")}>{m.value}</strong>
            </div>
          </div>
        );
      })}
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Activity, Box, Clock, Layers } from "lucide-react";

type Metric = { label: string; value: string; source: string };

export function FlowLabMetricsBar({
  stage,
  variant,
  refreshKey,
  visible,
}: {
  stage: string;
  variant: string;
  refreshKey: number;
  visible: boolean;
}) {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(false);
  const [wns, setWns] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!visible || stage === "rtl") return;
    setLoading(true);
    try {
      const [resR, resI] = await Promise.all([
        fetch(`/api/results?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}`),
        fetch(`/api/inspect?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}`),
      ]);
      if (resR.ok) {
        const data = await resR.json();
        setMetrics((data.metrics ?? []).slice(0, 4));
      }
      if (resI.ok) {
        const insp = await resI.json();
        setWns(insp.sta?.wns ?? null);
      }
    } catch {
      setMetrics([]);
    } finally {
      setLoading(false);
    }
  }, [stage, variant, visible]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  if (!visible || stage === "rtl") return null;

  return (
    <div className="fl-metrics" aria-busy={loading}>
      <div className="fl-metric-card">
        <Layers size={16} aria-hidden />
        <div>
          <span>Fase</span>
          <strong>{stage}</strong>
        </div>
      </div>
      {wns && (
        <div className="fl-metric-card accent">
          <Clock size={16} aria-hidden />
          <div>
            <span>WNS</span>
            <strong>{wns}</strong>
          </div>
        </div>
      )}
      {metrics.length === 0 && !loading && (
        <div className="fl-metric-card muted-card">
          <Box size={16} aria-hidden />
          <div>
            <span>Metriche</span>
            <strong>Esegui la fase</strong>
          </div>
        </div>
      )}
      {metrics.map((m) => (
        <div key={m.label} className="fl-metric-card">
          <Activity size={16} aria-hidden />
          <div>
            <span>{m.label}</span>
            <strong className={clsx(m.value.startsWith("-") && "warn")}>{m.value}</strong>
          </div>
        </div>
      ))}
    </div>
  );
}

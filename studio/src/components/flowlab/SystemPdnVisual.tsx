"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import styles from "./SystemPdnVisual.module.css";
import {
  SERIES,
  normalizeReport,
  type NormalizedReport,
  type SeriesKey,
  type WavePoint,
} from "./systemPdnReport";
import { SystemPdnSimulator } from "./SystemPdnSimulator";

type VisualTab = "tran" | "ac";

const CHART = {
  width: 820,
  height: 270,
  left: 54,
  right: 18,
  top: 22,
  bottom: 38,
};

function formatNumber(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatVoltage(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(4)} V`;
}

function formatTimeNs(value: number | null): string {
  if (value === null) return "—";
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(2)} µs`;
  return `${value.toFixed(value < 10 ? 2 : 1)} ns`;
}

function formatFrequency(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)} GHz`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)} MHz`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(2)} kHz`;
  return `${formatNumber(value, 1)} Hz`;
}

function statusClass(status: string): string {
  if (status === "PASS") return styles.statusOk;
  if (status === "FAIL" || status === "GAP") return styles.statusBad;
  return styles.statusWarn;
}

function sampleIndex<T extends { t: number }>(points: T[], target: number): number {
  let best = 0;
  let distance = Number.POSITIVE_INFINITY;
  points.forEach((point, index) => {
    const nextDistance = Math.abs(point.t - target);
    if (nextDistance < distance) {
      distance = nextDistance;
      best = index;
    }
  });
  return best;
}

function buildPath(
  points: WavePoint[],
  key: SeriesKey,
  xOf: (value: number) => number,
  yOf: (value: number) => number,
): string {
  let path = "";
  let open = false;
  for (const point of points) {
    const value = point.values[key];
    if (value === undefined) {
      open = false;
      continue;
    }
    path += `${open ? "L" : "M"}${xOf(point.t).toFixed(2)},${yOf(value).toFixed(2)} `;
    open = true;
  }
  return path.trim();
}

function chartPointX(event: { clientX: number }, element: SVGSVGElement): number {
  const bounds = element.getBoundingClientRect();
  const ratio = bounds.width > 0 ? (event.clientX - bounds.left) / bounds.width : 0;
  return CHART.left + Math.max(0, Math.min(1, ratio)) * (CHART.width - CHART.left - CHART.right);
}

function TranChart({
  report,
  visible,
  cursor,
  onCursor,
}: {
  report: NormalizedReport;
  visible: Record<SeriesKey, boolean>;
  cursor: number | null;
  onCursor: (index: number | null) => void;
}) {
  const activeSeries = SERIES.filter(
    (series) => visible[series.key] && report.wave.some((point) => point.values[series.key] !== undefined),
  );
  if (!report.wave.length || !activeSeries.length) {
    return <div className={styles.chartEmpty}>No voltage samples are available for the selected lanes.</div>;
  }

  const minT = report.wave[0]!.t;
  const maxT = report.wave[report.wave.length - 1]!.t;
  const tSpan = Math.max(maxT - minT, 1e-18);
  const values = activeSeries.flatMap((series) =>
    report.wave
      .map((point) => point.values[series.key])
      .filter((value): value is number => value !== undefined),
  );
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const pad = Math.max((rawMax - rawMin) * 0.12, 0.00001);
  const minV = rawMin - pad;
  const maxV = rawMax + pad;
  const vSpan = Math.max(maxV - minV, 0.00001);
  const plotW = CHART.width - CHART.left - CHART.right;
  const plotH = CHART.height - CHART.top - CHART.bottom;
  const xOf = (value: number) => CHART.left + ((value - minT) / tSpan) * plotW;
  const yOf = (value: number) => CHART.top + (1 - (value - minV) / vSpan) * plotH;
  const cursorPoint = cursor === null ? null : report.wave[Math.min(cursor, report.wave.length - 1)];
  const cursorX = cursorPoint ? xOf(cursorPoint.t) : null;
  const tooltipWidth = 188;
  const tooltipHeight = 38 + activeSeries.length * 14;
  const tooltipX = cursorX === null
    ? 0
    : Math.max(CHART.left + 4, Math.min(CHART.width - CHART.right - tooltipWidth, cursorX + 9));
  const tooltipY = CHART.top + 5;
  const dieBaseline = report.domains.find((domain) => domain.key === "die")?.baseline ?? null;
  const eventStart = report.delayNs === null ? null : xOf(minT + (report.delayNs * 1e-9));
  const eventEnd = report.delayNs === null || report.pulseWidthNs === null
    ? null
    : xOf(minT + ((report.delayNs + report.pulseWidthNs) * 1e-9));

  function onMove(event: React.MouseEvent<SVGSVGElement>) {
    const x = chartPointX(event, event.currentTarget);
    const t = minT + ((x - CHART.left) / plotW) * tSpan;
    onCursor(sampleIndex(report.wave, t));
  }

  return (
    <svg
      viewBox={`0 0 ${CHART.width} ${CHART.height}`}
      className={styles.chartSvg}
      role="img"
      aria-label="System PDN transient voltage waveform for VRM, board, package, and die"
      onMouseMove={onMove}
      onMouseLeave={() => onCursor(null)}
    >
      <rect x="0" y="0" width={CHART.width} height={CHART.height} rx="8" className={styles.chartBackground} />
      {eventStart !== null && eventEnd !== null && (
        <>
          <rect
            x={Math.max(CHART.left, eventStart)}
            y={CHART.top}
            width={Math.max(0, Math.min(CHART.width - CHART.right, eventEnd) - Math.max(CHART.left, eventStart))}
            height={plotH}
            className={styles.eventBand}
          />
          <text x={Math.max(CHART.left + 4, eventStart + 4)} y={CHART.top + 12} className={styles.eventLabel}>
            load step
          </text>
        </>
      )}
      {Array.from({ length: 6 }, (_, index) => {
        const ratio = index / 5;
        const y = CHART.top + ratio * plotH;
        const value = maxV - ratio * vSpan;
        return (
          <g key={`y-${index}`}>
            <line x1={CHART.left} y1={y} x2={CHART.width - CHART.right} y2={y} className={styles.gridLine} />
            <text x={CHART.left - 8} y={y + 3} textAnchor="end" className={styles.axisLabel}>
              {value.toFixed(4)}
            </text>
          </g>
        );
      })}
      {Array.from({ length: 6 }, (_, index) => {
        const ratio = index / 5;
        const x = CHART.left + ratio * plotW;
        const timeNs = (minT + ratio * tSpan) * 1e9;
        return (
          <g key={`x-${index}`}>
            <line x1={x} y1={CHART.top} x2={x} y2={CHART.top + plotH} className={styles.gridLine} />
            <text x={x} y={CHART.height - 13} textAnchor="middle" className={styles.axisLabel}>
              {formatTimeNs(timeNs)}
            </text>
          </g>
        );
      })}
      {dieBaseline !== null && (
        <line x1={CHART.left} y1={yOf(dieBaseline)} x2={CHART.width - CHART.right} y2={yOf(dieBaseline)} className={styles.baselineLine} />
      )}
      {activeSeries.map((series) => (
        <path key={series.key} d={buildPath(report.wave, series.key, xOf, yOf)} fill="none" stroke={series.color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      ))}
      {cursorPoint && cursorX !== null && (
        <>
          <line x1={cursorX} y1={CHART.top} x2={cursorX} y2={CHART.top + plotH} className={styles.cursorLine} />
          {activeSeries.map((series) => {
            const value = cursorPoint.values[series.key];
            return value === undefined ? null : <circle key={series.key} cx={cursorX} cy={yOf(value)} r="3.5" fill={series.color} stroke="#081019" strokeWidth="1.5" />;
          })}
          <g transform={`translate(${tooltipX}, ${tooltipY})`}>
            <rect width={tooltipWidth} height={tooltipHeight} rx="6" className={styles.tooltipBackground} />
            <text x="10" y="16" className={styles.tooltipTitle}>t = {formatTimeNs(cursorPoint.t * 1e9)}</text>
            {activeSeries.map((series, index) => {
              const value = cursorPoint.values[series.key];
              return value === undefined ? null : (
                <text key={series.key} x="10" y={33 + index * 14} className={styles.tooltipValue} fill={series.color}>
                  {series.label}: {formatVoltage(value)}
                </text>
              );
            })}
          </g>
        </>
      )}
      <text x={CHART.left} y={CHART.top - 8} className={styles.axisTitle}>voltage [V]</text>
      <text x={CHART.width - CHART.right} y={CHART.height - 2} textAnchor="end" className={styles.axisTitle}>time</text>
    </svg>
  );
}

function logTicks(minimum: number, maximum: number): number[] {
  const first = Math.ceil(Math.log10(minimum));
  const last = Math.floor(Math.log10(maximum));
  const ticks: number[] = [];
  for (let exponent = first; exponent <= last; exponent += 1) ticks.push(10 ** exponent);
  if (!ticks.length) return [minimum, maximum];
  return ticks;
}

function AcChart({
  report,
  cursor,
  onCursor,
}: {
  report: NormalizedReport;
  cursor: number | null;
  onCursor: (index: number | null) => void;
}) {
  if (!report.curve.length) {
    return <div className={styles.chartEmpty}>No AC impedance samples are available for this report.</div>;
  }

  const minF = report.curve[0]!.f;
  const maxF = report.curve[report.curve.length - 1]!.f;
  const minZRaw = Math.min(...report.curve.map((point) => point.z));
  const maxZRaw = Math.max(...report.curve.map((point) => point.z));
  const minZ = Math.max(minZRaw * 0.72, 0.001);
  const maxZ = Math.max(maxZRaw * 1.4, minZ * 2);
  const minLogF = Math.log10(minF);
  const maxLogF = Math.log10(maxF);
  const minLogZ = Math.log10(minZ);
  const maxLogZ = Math.log10(maxZ);
  const plotW = CHART.width - CHART.left - CHART.right;
  const plotH = CHART.height - CHART.top - CHART.bottom;
  const xOf = (value: number) => CHART.left + ((Math.log10(value) - minLogF) / (maxLogF - minLogF)) * plotW;
  const yOf = (value: number) => CHART.top + (1 - (Math.log10(value) - minLogZ) / (maxLogZ - minLogZ)) * plotH;
  const path = report.curve.map((point, index) => `${index ? "L" : "M"}${xOf(point.f).toFixed(2)},${yOf(point.z).toFixed(2)}`).join(" ");
  const cursorPoint = cursor === null ? null : report.curve[Math.min(cursor, report.curve.length - 1)];
  const cursorX = cursorPoint ? xOf(cursorPoint.f) : null;
  const tooltipWidth = 194;
  const tooltipX = cursorX === null
    ? 0
    : Math.max(CHART.left + 4, Math.min(CHART.width - CHART.right - tooltipWidth, cursorX + 9));
  const targetY = report.zTargetMOhm && report.zTargetMOhm > 0 ? yOf(report.zTargetMOhm) : null;
  const zmaxX = report.fAtZMax && report.fAtZMax > 0 ? xOf(report.fAtZMax) : null;
  const zmaxY = report.zMaxMOhm && report.zMaxMOhm > 0 ? yOf(report.zMaxMOhm) : null;
  const fTicks = logTicks(minF, maxF);
  const zTicks = logTicks(minZ, maxZ);

  function onMove(event: React.MouseEvent<SVGSVGElement>) {
    const x = chartPointX(event, event.currentTarget);
    const logFrequency = minLogF + ((x - CHART.left) / plotW) * (maxLogF - minLogF);
    const frequency = 10 ** logFrequency;
    onCursor(sampleIndex(report.curve.map((point) => ({ t: point.f })), frequency));
  }

  return (
    <svg
      viewBox={`0 0 ${CHART.width} ${CHART.height}`}
      className={styles.chartSvg}
      role="img"
      aria-label="System PDN AC impedance curve with target and resonance markers"
      onMouseMove={onMove}
      onMouseLeave={() => onCursor(null)}
    >
      <rect x="0" y="0" width={CHART.width} height={CHART.height} rx="8" className={styles.chartBackground} />
      {zTicks.map((tick) => {
        const y = yOf(tick);
        return (
          <g key={`z-${tick}`}>
            <line x1={CHART.left} y1={y} x2={CHART.width - CHART.right} y2={y} className={styles.gridLine} />
            <text x={CHART.left - 8} y={y + 3} textAnchor="end" className={styles.axisLabel}>{formatNumber(tick, tick < 1 ? 3 : 0)}</text>
          </g>
        );
      })}
      {fTicks.map((tick) => {
        const x = xOf(tick);
        return (
          <g key={`f-${tick}`}>
            <line x1={x} y1={CHART.top} x2={x} y2={CHART.top + plotH} className={styles.gridLine} />
            <text x={x} y={CHART.height - 13} textAnchor="middle" className={styles.axisLabel}>{formatFrequency(tick)}</text>
          </g>
        );
      })}
      {targetY !== null && (
        <>
          <line x1={CHART.left} y1={targetY} x2={CHART.width - CHART.right} y2={targetY} className={styles.targetLine} />
          <text x={CHART.width - CHART.right - 4} y={targetY - 6} textAnchor="end" className={styles.targetLabel}>Ztarget {formatNumber(report.zTargetMOhm, 1)} mΩ</text>
        </>
      )}
      <path d={path} fill="none" stroke="#68c7ff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      {report.peaks.slice(0, 5).map((peak) => {
        if (peak.f < minF || peak.f > maxF || peak.z < minZ || peak.z > maxZ) return null;
        const x = xOf(peak.f);
        const y = yOf(peak.z);
        return (
          <g key={`${peak.f}-${peak.z}`}>
            <circle cx={x} cy={y} r="4" fill="#ff8b65" stroke="#081019" strokeWidth="1.5" />
            <text x={x + 6} y={y - 7} className={styles.peakLabel}>{formatFrequency(peak.f)}</text>
          </g>
        );
      })}
      {zmaxX !== null && zmaxY !== null && zmaxX >= CHART.left && zmaxX <= CHART.width - CHART.right && zmaxY >= CHART.top && zmaxY <= CHART.top + plotH && (
        <g>
          <circle cx={zmaxX} cy={zmaxY} r="5" fill="#ff8b65" stroke="#081019" strokeWidth="2" />
          <text x={Math.min(CHART.width - CHART.right - 4, zmaxX + 8)} y={Math.max(CHART.top + 12, zmaxY - 9)} textAnchor={zmaxX > CHART.width * 0.78 ? "end" : "start"} className={styles.peakLabel}>Zmax</text>
        </g>
      )}
      {cursorPoint && cursorX !== null && (
        <>
          <line x1={cursorX} y1={CHART.top} x2={cursorX} y2={CHART.top + plotH} className={styles.cursorLine} />
          <circle cx={cursorX} cy={yOf(cursorPoint.z)} r="3.5" fill="#68c7ff" stroke="#081019" strokeWidth="1.5" />
          <g transform={`translate(${tooltipX}, ${CHART.top + 5})`}>
            <rect width={tooltipWidth} height="56" rx="6" className={styles.tooltipBackground} />
            <text x="10" y="16" className={styles.tooltipTitle}>f = {formatFrequency(cursorPoint.f)}</text>
            <text x="10" y="33" className={styles.tooltipValue} fill="#68c7ff">|Z| = {formatNumber(cursorPoint.z, 2)} mΩ</text>
            <text x="10" y="49" className={styles.tooltipValue} fill="#9aabba">phase = {cursorPoint.phase === null ? "—" : `${cursorPoint.phase.toFixed(1)}°`}</text>
          </g>
        </>
      )}
      <text x={CHART.left} y={CHART.top - 8} className={styles.axisTitle}>|Z| [mΩ] · log</text>
      <text x={CHART.width - CHART.right} y={CHART.height - 2} textAnchor="end" className={styles.axisTitle}>frequency · log</text>
    </svg>
  );
}

function DomainRail({ report }: { report: NormalizedReport }) {
  const maxDroop = Math.max(...report.domains.map((domain) => domain.droopMv ?? 0), 0.001);
  return (
    <div className={styles.domainRail}>
      <div className={styles.inspectorHeading}>
        <span>Rail ladder</span>
        <small>ΔV at die minimum</small>
      </div>
      {report.domains.map((domain) => (
        <div className={styles.domainRow} key={domain.key}>
          <div className={styles.domainRowHead}>
            <span>{domain.label}</span>
            <strong>{formatNumber(domain.droopMv, 3)} mV</strong>
          </div>
          <div className={styles.domainTrack} aria-hidden="true">
            <i style={{ width: `${Math.min(100, ((domain.droopMv ?? 0) / maxDroop) * 100)}%` }} />
          </div>
          <small>
            {domain.minimum === null ? "minimum —" : `min ${formatVoltage(domain.minimum)}`}
            {domain.settled === true ? " · settled" : domain.settled === false ? " · not settled" : ""}
          </small>
        </div>
      ))}
    </div>
  );
}

function PathDropRail({ report }: { report: NormalizedReport }) {
  if (!report.pathDrops.length) return null;
  const max = Math.max(...report.pathDrops.map((drop) => drop.valueMv), 0.001);
  return (
    <div className={styles.pathRail}>
      <div className={styles.inspectorHeading}>
        <span>Path drops</span>
        <small>at transient peak</small>
      </div>
      {report.pathDrops.map((drop) => (
        <div className={styles.pathRow} key={drop.label}>
          <span>{drop.label}</span>
          <div className={styles.pathTrack} aria-hidden="true"><i style={{ width: `${Math.min(100, (drop.valueMv / max) * 100)}%` }} /></div>
          <strong>{formatNumber(drop.valueMv, 3)} mV</strong>
        </div>
      ))}
    </div>
  );
}

export function SystemPdnVisual({
  reportPath = "sim/reports/system_pdn_flowlab.json",
  refreshKey,
  compact = false,
}: {
  reportPath?: string;
  refreshKey?: number;
  compact?: boolean;
}) {
  const [baselineReport, setBaselineReport] = useState<NormalizedReport | null>(null);
  const [scenarioReport, setScenarioReport] = useState<NormalizedReport | null>(null);
  const [scenarioRunId, setScenarioRunId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<"baseline" | "scenario">("baseline");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<VisualTab>("tran");
  const [cursor, setCursor] = useState<number | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [visible, setVisible] = useState<Record<SeriesKey, boolean>>(() =>
    Object.fromEntries(SERIES.map((series) => [series.key, true])) as Record<SeriesKey, boolean>,
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/content?path=${encodeURIComponent(reportPath)}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`report unavailable (HTTP ${response.status})`);
      const body = (await response.json()) as { content?: string };
      const next = normalizeReport(JSON.parse(body.content ?? ""));
      if (!next) throw new Error("report payload is not a System PDN report");
      setBaselineReport(next);
      setCursor(null);
    } catch (cause) {
      setBaselineReport(null);
      setError(cause instanceof Error ? cause.message : "System PDN report unavailable");
    } finally {
      setLoading(false);
    }
  }, [reportPath]);

  useEffect(() => {
    void load();
  }, [load, refreshKey, reloadKey]);

  useEffect(() => {
    const onEvent = (event: Event) => {
      const detail = (event as CustomEvent<{ type?: string }>).detail;
      if (["tool.completed", "tool.failed", "artifact.changed", "report.updated"].includes(detail?.type ?? "")) {
        setReloadKey((value) => value + 1);
      }
    };
    window.addEventListener("pdflow:agent-event", onEvent);
    return () => window.removeEventListener("pdflow:agent-event", onEvent);
  }, []);

  const reportId = useMemo(
    () => reportPath.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "system-pdn",
    [reportPath],
  );
  const report = activeView === "scenario" && scenarioReport
    ? scenarioReport
    : baselineReport;
  const currentStatus = report?.status ?? (loading ? "LOADING" : "NOT_RUN");

  function toggleSeries(key: SeriesKey) {
    setVisible((current) => ({ ...current, [key]: !current[key] }));
    setCursor(null);
  }

  function handleScenarioLoaded(
    raw: unknown,
    runId: string,
  ): boolean {
    const next = normalizeReport(raw);
    if (!next) return false;
    setScenarioReport(next);
    setScenarioRunId(runId);
    setActiveView("scenario");
    setCursor(null);
    return true;
  }

  const simulatorVariant = baselineReport?.variant || "flowlab";

  return (
    <section className={`${styles.visual} ${compact ? styles.compact : ""}`} aria-label="System PDN visual analysis">
      <header className={styles.header}>
        <div className={styles.headerCopy}>
          <span className={styles.kicker}>System PDN · live viewport</span>
          <h2>TRAN / AC waveform</h2>
          <p>Voltage propagation through the VRM → board → package → die ladder, paired with the AC impedance sweep.</p>
        </div>
        <div className={styles.headerActions}>
          <span className={`${styles.status} ${statusClass(currentStatus)}`}>{currentStatus}</span>
          <button type="button" className={styles.refreshButton} onClick={() => setReloadKey((value) => value + 1)} disabled={loading}>
            <RefreshCw size={13} aria-hidden className={loading ? styles.spinning : ""} />
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </header>

      {error && <p className={styles.error} role="alert">System PDN visual unavailable: {error}</p>}

      <SystemPdnSimulator
        variant={simulatorVariant}
        baseline={baselineReport}
        scenario={scenarioReport}
        scenarioRunId={scenarioRunId}
        activeView={activeView}
        onScenarioLoaded={handleScenarioLoaded}
        onSelectView={setActiveView}
      />

      {report && (
        <>
          <div className={styles.statGrid}>
            <div className={styles.statCard}>
              <span>Die droop</span>
              <strong>{formatNumber(report.droopMv, 3)} mV</strong>
              <small>{formatNumber(report.droopPct, 3)}% of VDD · peak {formatTimeNs(report.peakAtNs)}</small>
            </div>
            <div className={styles.statCard}>
              <span>Zmax</span>
              <strong>{formatNumber(report.zMaxMOhm, 2)} mΩ</strong>
              <small>{formatFrequency(report.fAtZMax)} · target {formatNumber(report.zTargetMOhm, 1)} mΩ</small>
            </div>
            <div className={styles.statCard}>
              <span>Die current</span>
              <strong>{formatNumber(report.iAvgMa, 3)} mA</strong>
              <small>{report.currentSource} · VDD {formatNumber(report.vdd, 3)} V</small>
            </div>
            <div className={styles.statCard}>
              <span>Evidence</span>
              <strong className={report.evidenceOk === true ? styles.goodText : styles.warnText}>{report.evidenceClass}</strong>
              <small>{report.productSignoff === true ? "Product eligible" : "Package / Lab only"}</small>
            </div>
          </div>

          <div className={styles.workspace}>
            <div className={styles.chartPanel}>
              <div className={styles.chartToolbar}>
                <div className={styles.tabs} role="tablist" aria-label="System PDN plots">
                  <button type="button" role="tab" id={`${reportId}-tab-tran`} aria-controls={`${reportId}-panel-tran`} aria-selected={tab === "tran"} className={tab === "tran" ? styles.tabActive : styles.tab} onClick={() => { setTab("tran"); setCursor(null); }}>
                    TRAN · waveform
                  </button>
                  <button type="button" role="tab" id={`${reportId}-tab-ac`} aria-controls={`${reportId}-panel-ac`} aria-selected={tab === "ac"} className={tab === "ac" ? styles.tabActive : styles.tab} onClick={() => { setTab("ac"); setCursor(null); }}>
                    AC · Z(f)
                  </button>
                </div>
                <span className={styles.plotHint}>{tab === "tran" ? `${report.wave.length} samples · hover for cursor` : `${report.curve.length} points · log frequency / magnitude`}</span>
              </div>

              {tab === "tran" ? (
                <div id={`${reportId}-panel-tran`} role="tabpanel" aria-labelledby={`${reportId}-tab-tran`}>
                  <TranChart report={report} visible={visible} cursor={cursor} onCursor={setCursor} />
                  <div className={styles.legend} aria-label="Waveform lanes">
                    {SERIES.map((series) => {
                      const available = report.wave.some((point) => point.values[series.key] !== undefined);
                      return (
                        <button key={series.key} type="button" className={`${styles.legendButton} ${visible[series.key] ? styles.legendOn : styles.legendOff}`} aria-pressed={visible[series.key]} disabled={!available} onClick={() => toggleSeries(series.key)}>
                          <i style={{ backgroundColor: series.color }} /> {series.label}
                        </button>
                      );
                    })}
                    <span className={styles.legendNote}>baseline — · load-step band</span>
                  </div>
                </div>
              ) : (
                <div id={`${reportId}-panel-ac`} role="tabpanel" aria-labelledby={`${reportId}-tab-ac`}>
                  <AcChart report={report} cursor={cursor} onCursor={setCursor} />
                  <div className={styles.legend}>
                    <span className={styles.legendStatic}><i className={styles.legendLine} /> |Z|</span>
                    <span className={styles.legendStatic}><i className={styles.legendTarget} /> configured Ztarget</span>
                    <span className={styles.legendStatic}><i className={styles.legendPeak} /> resonance / Zmax</span>
                  </div>
                </div>
              )}
              <p className={styles.chartCaption}>
                {tab === "tran"
                  ? "The plotted lanes are ngspice TRAN node voltages. The narrow rail separation is intentionally auto-scaled so the die disturbance remains visible."
                  : "The AC plot uses logarithmic axes. The target line is a requirement overlay; a WARN or PROXY result is not Product signoff."}
              </p>
            </div>

            <aside className={styles.inspector} aria-label="System PDN plot inspector">
              <DomainRail report={report} />
              <PathDropRail report={report} />
              <div className={styles.checkRail}>
                <div className={styles.inspectorHeading}><span>Checks</span><small>same invocation</small></div>
                <div className={styles.checkRow}><span>TRAN measurement</span><strong className={report.wave.length ? styles.goodText : styles.warnText}>{report.wave.length ? "READY" : "GAP"}</strong></div>
                <div className={styles.checkRow}><span>AC measurement</span><strong className={report.curve.length ? styles.goodText : styles.warnText}>{report.curve.length ? "READY" : "GAP"}</strong></div>
                <div className={styles.checkRow}><span>Ztarget</span><strong className={report.targetPass === true ? styles.goodText : styles.warnText}>{report.targetPass === true ? "PASS" : report.targetPass === false ? "WARN" : "—"}</strong></div>
                <div className={styles.checkRow}><span>Settling</span><strong>{report.settlingNs === null ? "—" : formatTimeNs(report.settlingNs)}</strong></div>
              </div>
            </aside>
          </div>

          <details className={styles.provenance}>
            <summary>Run / provenance · {report.variant} · {report.runId}</summary>
            <div className={styles.provenanceGrid}>
              <span>run_id</span><code>{report.runId}</code>
              <span>mesh_id</span><code>{report.meshId}</code>
              <span>generated</span><code>{report.generatedAt}</code>
              <span>inputs</span><code>{report.inputCount} artifacts · {report.currentSource}</code>
            </div>
            <p>{report.summary}</p>
          </details>
        </>
      )}
    </section>
  );
}

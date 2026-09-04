"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import type { FlowlabParams } from "./types";
import { FlowLabLayoutCanvas } from "./FlowLabLayoutCanvas";
import { RtlWaveformVisual } from "./RtlWaveformVisual";

type Inspect = {
  odb: {
    design: string;
    instances: number;
    nets: number;
    dieDbu: { dx: number; dy: number };
  } | null;
  sta: {
    wns?: string;
    tns?: string;
    worstSlack?: string;
    paths: { endpoint: string; slack: string; status: string }[];
  } | null;
  yosys: { cells?: string; area?: string; dff?: string } | null;
};

type Results = {
  metrics: { label: string; value: string }[];
  goldenHints: { label: string; value: string }[];
  artifacts: { name: string; exists: boolean; size: number }[];
};

function parseNum(s?: string) {
  if (!s) return null;
  const n = parseFloat(s.replace(/[^\d.-]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function Gauge({
  label,
  value,
  min,
  max,
  unit,
  good,
}: {
  label: string;
  value: number | null;
  min: number;
  max: number;
  unit?: string;
  good?: "high" | "low";
}) {
  const pct =
    value == null ? 0 : Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  const ok =
    value == null
      ? null
      : good === "high"
        ? value >= max * 0.85
        : good === "low"
          ? value <= min + (max - min) * 0.15
          : null;
  return (
    <div className="fl-vis-gauge">
      <div className="fl-vis-gauge-head">
        <span>{label}</span>
        <strong className={clsx(ok === false && "warn", ok === true && "ok")}>
          {value == null ? "—" : `${value.toFixed(2)}${unit ?? ""}`}
        </strong>
      </div>
      <div className="fl-vis-gauge-track">
        <i style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function StatBar({
  label,
  value,
  golden,
  max,
}: {
  label: string;
  value: number | null;
  golden?: number;
  max: number;
}) {
  const v = value ?? 0;
  const pct = Math.min(100, (v / max) * 100);
  const gPct = golden ? Math.min(100, (golden / max) * 100) : null;
  return (
    <div className="fl-vis-bar">
      <div className="fl-vis-bar-head">
        <span>{label}</span>
        <strong>{value ?? "—"}</strong>
      </div>
      <div className="fl-vis-bar-track">
        {gPct != null && <em style={{ left: `${gPct}%` }} title={`Golden ${golden}`} />}
        <i style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ClockTreeViz({ paths }: { paths: { endpoint: string; slack: string; status: string }[] }) {
  const nodes = paths.slice(0, 5);
  return (
    <svg viewBox="0 0 320 140" className="fl-vis-cts" aria-label="Clock tree paths">
      <line x1="160" y1="20" x2="160" y2="50" stroke="#58a6ff" strokeWidth="2" />
      <circle cx="160" cy="16" r="8" fill="#f0883e" />
      <text x="160" y="19" textAnchor="middle" fill="#0a0e14" fontSize="7" fontWeight="bold">
        CLK
      </text>
      {nodes.map((p, i) => {
        const x = 40 + (i * 240) / Math.max(nodes.length - 1, 1);
        const met = p.status === "MET";
        return (
          <g key={p.endpoint}>
            <line x1="160" y1="50" x2={x} y2="90" stroke="rgba(88,166,255,0.5)" strokeWidth="1.5" />
            <circle cx={x} cy="100" r="10" fill={met ? "rgba(63,185,80,0.3)" : "rgba(248,81,73,0.3)"} stroke={met ? "#3fb950" : "#f85149"} />
            <text x={x} y="103" textAnchor="middle" fill="#e6edf3" fontSize="6">
              {p.slack}
            </text>
            <text x={x} y="125" textAnchor="middle" fill="#8b949e" fontSize="5">
              {p.endpoint.slice(0, 12)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function FlowLabPhaseVisual({
  phaseId,
  stage,
  variant,
  params,
  refreshKey,
  rtlLines,
  sim,
  stageDone,
}: {
  phaseId: string;
  stage: string;
  variant: string;
  params: FlowlabParams;
  refreshKey: number;
  rtlLines: number;
  sim: { vcdExists: boolean; logExists: boolean };
  stageDone: boolean;
}) {
  const [inspect, setInspect] = useState<Inspect | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [loading, setLoading] = useState(false);
  const [meshStats, setMeshStats] = useState<{
    resistors?: number;
    current_sources?: number;
    voltage_sources?: number;
  } | null>(null);

  const load = useCallback(async () => {
    if (phaseId === "rtl") return;
    setLoading(true);
    try {
      const [ri, rr] = await Promise.all([
        fetch(`/api/inspect?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}`),
        fetch(`/api/results?stage=${encodeURIComponent(stage)}&variant=${encodeURIComponent(variant)}`),
      ]);
      setInspect(ri.ok ? await ri.json() : null);
      setResults(rr.ok ? await rr.json() : null);
      if (phaseId === "pdn") {
        const rm = await fetch(
          `/api/content?path=${encodeURIComponent(`sim/spice/mesh_stats_${variant}.json`)}`,
        );
        if (rm.ok) {
          const body = await rm.json();
          try {
            setMeshStats(JSON.parse(body.content));
          } catch {
            setMeshStats(null);
          }
        } else {
          setMeshStats(null);
        }
      }
    } finally {
      setLoading(false);
    }
  }, [phaseId, stage, variant]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const golden = Object.fromEntries(
    (results?.goldenHints ?? []).map((g) => [g.label.toLowerCase(), parseNum(g.value)]),
  );
  const cells = parseNum(inspect?.yosys?.cells);
  const area = parseNum(inspect?.yosys?.area);
  const wns = parseNum(inspect?.sta?.wns);
  const tns = parseNum(inspect?.sta?.tns);

  return (
    <div className={clsx("fl-phase-visual", loading && "loading")} aria-busy={loading}>
      <div className="fl-vis-header">
        <span className="fl-vis-kicker">FlowLab viewport</span>
        <span className={clsx("fl-vis-badge", stageDone ? "done" : "pending")}>
          {stageDone ? "Artifact present" : "Run to populate"}
        </span>
      </div>

      {phaseId === "rtl" && <RtlWaveformVisual rtlLines={rtlLines} sim={sim} />}

      {(phaseId === "synth" ||
        phaseId === "floorplan" ||
        phaseId === "pdn" ||
        phaseId === "place" ||
        phaseId === "cts" ||
        phaseId === "route" ||
        phaseId === "finish") && (
        <FlowLabLayoutCanvas
          phaseId={phaseId as "synth" | "floorplan" | "pdn" | "place" | "cts" | "route" | "finish"}
          variant={variant}
          refreshKey={refreshKey}
          stageDone={stageDone}
        />
      )}

      {phaseId === "synth" && (
        <div className="fl-vis-body fl-vis-synth fl-vis-stats-only">
          <StatBar label="Yosys cells" value={cells} golden={golden.celle ?? golden.cells ?? undefined} max={600} />
          <StatBar label="Area" value={area} golden={golden.area ?? undefined} max={700} />
          <StatBar label="DFF_X1" value={parseNum(inspect?.yosys?.dff)} golden={golden.dff ?? undefined} max={50} />
          {inspect?.odb && (
            <p className="fl-vis-meta">
              ODB: {inspect.odb.instances} inst · {inspect.odb.nets} net
            </p>
          )}
        </div>
      )}

      {phaseId === "floorplan" && (
        <div className="fl-vis-body fl-vis-stats-only">
          <div className="fl-vis-side-stats fl-vis-side-stats-row">
            <Gauge label="Core util (param)" value={params.coreUtilization} min={20} max={55} unit="%" />
            {inspect?.odb && (
              <>
                <div className="fl-vis-stat">
                  <span>Instances</span>
                  <strong>{inspect.odb.instances}</strong>
                </div>
                <div className="fl-vis-stat">
                  <span>Nets</span>
                  <strong>{inspect.odb.nets}</strong>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {phaseId === "place" && (
        <div className="fl-vis-body fl-vis-stats-only">
          <p className="fl-vis-meta">
            Density addon {params.placeDensityAddon.toFixed(2)} ·{" "}
            {inspect?.odb ? `${inspect.odb.instances} placed cells` : "Run placement"}
          </p>
        </div>
      )}

      {phaseId === "cts" && (
        <div className="fl-vis-body fl-vis-cts fl-vis-stats-only">
          <ClockTreeViz paths={inspect?.sta?.paths ?? []} />
          <div className="fl-vis-gauge-row">
            <Gauge label="WNS" value={wns} min={-0.5} max={0.1} unit=" ns" good="high" />
            <Gauge label="TNS" value={tns} min={-10} max={0} unit=" ns" good="high" />
            <Gauge label="TNS end %" value={params.tnsEndPercent} min={0} max={100} unit="%" />
          </div>
        </div>
      )}

      {phaseId === "route" && (
        <div className="fl-vis-body fl-vis-stats-only">
          <div className="fl-vis-stat-grid">
            <div className="fl-vis-stat">
              <span>Nets</span>
              <strong>{inspect?.odb?.nets ?? "—"}</strong>
            </div>
            <div className="fl-vis-stat">
              <span>Worst slack</span>
              <strong className={wns != null && wns < 0 ? "warn" : ""}>
                {inspect?.sta?.worstSlack ?? "—"}
              </strong>
            </div>
          </div>
        </div>
      )}

      {phaseId === "finish" && (
        <div className="fl-vis-body fl-vis-finish fl-vis-stats-only">
          <ul className="fl-vis-checklist">
            {["6_final.gds", "6_final.spef", "6_final.def", "6_final.v"].map((name) => {
              const a = results?.artifacts.find((x) => x.name === name);
              return (
                <li key={name} className={a?.exists ? "ok" : ""}>
                  <span>{a?.exists ? "✓" : "○"}</span>
                  <code>{name}</code>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {phaseId === "pdn" && (
        <div className="fl-vis-body fl-vis-pdn fl-vis-stats-only">
          <div className="fl-vis-stat-grid">
            <div className="fl-vis-stat">
              <span>ODB PDN</span>
              <strong className={stageDone ? "ok" : ""}>
                {inspect?.odb ? "OK" : stageDone ? "verified" : "—"}
              </strong>
            </div>
            <div className="fl-vis-stat">
              <span>Instances</span>
              <strong>{inspect?.odb?.instances ?? "—"}</strong>
            </div>
            <div className="fl-vis-stat">
              <span>Gridcheck</span>
              <strong className={stageDone ? "ok" : ""}>
                {stageDone ? "PSM-0040" : "Run"}
              </strong>
            </div>
            {meshStats && (
              <div className="fl-vis-stat">
                <span>Mesh SPICE</span>
                <strong>
                  {meshStats.resistors?.toLocaleString()} R · {meshStats.current_sources} I
                </strong>
              </div>
            )}
          </div>
          {meshStats ? (
            <p className="fl-vis-meta">
              Mesh export · <code>learn/sim/spice/</code> ·{" "}
              <Link href="/materials/reference/spice-chip-mesh.md">docs mesh</Link>
            </p>
          ) : (
            <p className="fl-vis-meta">
              After finish: chip IR → <code>write_pg_spice</code> ·{" "}
              <Link href="/materials/reference/spice-chip-mesh.md">mesh SPICE</Link>
            </p>
          )}
        </div>
      )}

    </div>
  );
}

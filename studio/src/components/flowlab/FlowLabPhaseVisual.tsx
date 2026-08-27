"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import type { FlowlabParams } from "./types";
import { PHASES } from "./phases";

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

function DieCanvas({
  util,
  dieDbu,
  label,
}: {
  util: number;
  dieDbu?: { dx: number; dy: number };
  label: string;
}) {
  const aspect =
    dieDbu && dieDbu.dx > 0 && dieDbu.dy > 0 ? dieDbu.dx / dieDbu.dy : 1.35;
  const w = 280;
  const h = w / aspect;
  const corePct = util / 100;
  const margin = 12;
  const innerW = w - margin * 2;
  const innerH = h - margin * 2;
  const coreW = innerW * Math.sqrt(corePct);
  const coreH = innerH * Math.sqrt(corePct);
  const cx = (w - coreW) / 2;
  const cy = (h - coreH) / 2;

  return (
    <div className="fl-vis-die-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} className="fl-vis-die" aria-label={label}>
        <defs>
          <pattern id="fl-die-grid" width="8" height="8" patternUnits="userSpaceOnUse">
            <path d="M 8 0 L 0 0 0 8" fill="none" stroke="rgba(88,166,255,0.15)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect x="1" y="1" width={w - 2} height={h - 2} rx="6" fill="#0a0e14" stroke="rgba(255,255,255,0.12)" />
        <rect x={margin} y={margin} width={innerW} height={innerH} rx="4" fill="url(#fl-die-grid)" stroke="rgba(255,255,255,0.08)" />
        <rect
          x={cx}
          y={cy}
          width={coreW}
          height={coreH}
          rx="3"
          fill="rgba(240,136,62,0.35)"
          stroke="rgba(240,136,62,0.75)"
          strokeWidth="1.5"
        />
        <text x={w / 2} y={h - 4} textAnchor="middle" fill="#8b949e" fontSize="9">
          core {util}%
        </text>
        {dieDbu && dieDbu.dx > 0 && (
          <text x={w / 2} y="11" textAnchor="middle" fill="#58a6ff" fontSize="8">
            {Math.round(dieDbu.dx / 1000)}×{Math.round(dieDbu.dy / 1000)} kDBU
          </text>
        )}
      </svg>
      <p className="fl-vis-die-caption">{label}</p>
    </div>
  );
}

function PipelineMini({ activeId }: { activeId: string }) {
  return (
    <div className="fl-vis-pipeline" aria-hidden>
      {PHASES.map((p, i) => (
        <span key={p.id} className={clsx("fl-vis-pip", p.id === activeId && "active", i < PHASES.findIndex((x) => x.id === activeId) && "done")}>
          {p.label}
        </span>
      ))}
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

function RtlVisual({
  rtlLines,
  sim,
}: {
  rtlLines: number;
  sim: { vcdExists: boolean; logExists: boolean };
}) {
  return (
    <div className="fl-vis-rtl">
      <div className="fl-vis-stat-grid">
        <div className="fl-vis-stat">
          <span>Righe RTL</span>
          <strong>{rtlLines}</strong>
        </div>
        <div className="fl-vis-stat">
          <span>Sim log</span>
          <strong className={sim.logExists ? "ok" : ""}>{sim.logExists ? "OK" : "—"}</strong>
        </div>
        <div className="fl-vis-stat">
          <span>VCD</span>
          <strong className={sim.vcdExists ? "ok" : ""}>{sim.vcdExists ? "Pronto" : "—"}</strong>
        </div>
      </div>
      <svg viewBox="0 0 400 80" className="fl-vis-wave" aria-label="Waveform preview">
        <rect width="400" height="80" rx="8" fill="#0a0e14" />
        {[0, 1, 2].map((lane) => (
          <polyline
            key={lane}
            fill="none"
            stroke={lane === 0 ? "#f0883e" : lane === 1 ? "#58a6ff" : "#3fb950"}
            strokeWidth="1.5"
            points={Array.from({ length: 40 }, (_, i) => {
              const x = 10 + i * 9.5;
              const y = 20 + lane * 22 + (Math.sin(i * 0.7 + lane) > 0 ? 0 : 14);
              return `${x},${y}`;
            }).join(" ")}
          />
        ))}
        <text x="200" y="74" textAnchor="middle" fill="#484f58" fontSize="8">
          {sim.vcdExists ? "Waveform da gcd.vcd" : "Esegui sim per waveform"}
        </text>
      </svg>
    </div>
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
  const [pdnReport, setPdnReport] = useState<{
    summary?: string;
    kind?: string;
    engine?: string;
    transient?: {
      droop_mv?: number;
      droop_pct?: number;
      worst_droop?: number;
      worst_droop_pct?: number;
    };
    impedance?: {
      z_max_mohm?: number;
      f_at_zmax_hz?: number;
      z_target_mohm?: number;
      pass_target?: boolean | null;
    };
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
      if (phaseId === "pkg") {
        const paths = [
          `sim/reports/system_pdn_${variant}.json`,
          `sim/reports/pdn_chip_ir_${variant}.json`,
          `sim/reports/pdn_transient_${variant}.json`,
        ];
        let loaded = null as typeof pdnReport;
        for (const p of paths) {
          const rp = await fetch(`/api/content?path=${encodeURIComponent(p)}`);
          if (!rp.ok) continue;
          const body = await rp.json();
          try {
            const parsed = JSON.parse(body.content);
            loaded = parsed;
            if (parsed?.kind === "system_pdn" || parsed?.engine === "ngspice-hierarchical") {
              break;
            }
          } catch {
            /* try next */
          }
        }
        setPdnReport(loaded);
      }
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
        <PipelineMini activeId={phaseId} />
        <span className={clsx("fl-vis-badge", stageDone ? "done" : "pending")}>
          {stageDone ? "Artefatto presente" : "Esegui per popolare"}
        </span>
      </div>

      {phaseId === "rtl" && <RtlVisual rtlLines={rtlLines} sim={sim} />}

      {phaseId === "synth" && (
        <div className="fl-vis-body fl-vis-synth">
          <StatBar label="Celle Yosys" value={cells} golden={golden.celle ?? golden.cells ?? undefined} max={600} />
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
        <div className="fl-vis-body fl-vis-floorplan">
          <DieCanvas
            util={params.coreUtilization}
            dieDbu={inspect?.odb?.dieDbu}
            label={`Floorplan · util ${params.coreUtilization}%`}
          />
          <div className="fl-vis-side-stats">
            <Gauge label="Core util (param)" value={params.coreUtilization} min={20} max={55} unit="%" />
            {inspect?.odb && (
              <>
                <div className="fl-vis-stat">
                  <span>Istanze</span>
                  <strong>{inspect.odb.instances}</strong>
                </div>
                <div className="fl-vis-stat">
                  <span>Reti</span>
                  <strong>{inspect.odb.nets}</strong>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {phaseId === "place" && (
        <div className="fl-vis-body fl-vis-place">
          <DieCanvas util={params.coreUtilization + params.placeDensityAddon * 40} dieDbu={inspect?.odb?.dieDbu} label="Placement density" />
          <div className="fl-vis-place-grid" aria-hidden>
            {Array.from({ length: 48 }).map((_, i) => (
              <span
                key={i}
                className={clsx("fl-vis-cell", i % 7 === 0 && "macro")}
                style={{ opacity: 0.35 + (i % 5) * 0.12 }}
              />
            ))}
          </div>
          <p className="fl-vis-meta">
            Density addon {params.placeDensityAddon.toFixed(2)} ·{" "}
            {inspect?.odb ? `${inspect.odb.instances} celle piazzate` : "Run placement"}
          </p>
        </div>
      )}

      {phaseId === "cts" && (
        <div className="fl-vis-body fl-vis-cts">
          <ClockTreeViz paths={inspect?.sta?.paths ?? []} />
          <div className="fl-vis-gauge-row">
            <Gauge label="WNS" value={wns} min={-0.5} max={0.1} unit=" ns" good="high" />
            <Gauge label="TNS" value={tns} min={-10} max={0} unit=" ns" good="high" />
            <Gauge label="TNS end %" value={params.tnsEndPercent} min={0} max={100} unit="%" />
          </div>
        </div>
      )}

      {phaseId === "route" && (
        <div className="fl-vis-body fl-vis-route">
          <div className="fl-vis-layer-stack">
            {["M1", "M2", "M3", "M4", "M5", "M6"].map((layer, i) => (
              <div key={layer} className="fl-vis-layer" style={{ "--i": i } as React.CSSProperties}>
                <span>{layer}</span>
                <i />
              </div>
            ))}
          </div>
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
        <div className="fl-vis-body fl-vis-finish">
          <div className="fl-vis-chip">
            <svg viewBox="0 0 120 120" aria-hidden>
              <rect x="8" y="8" width="104" height="104" rx="8" fill="#0a0e14" stroke="#f0883e" strokeWidth="2" />
              <rect x="24" y="24" width="72" height="72" rx="4" fill="rgba(240,136,62,0.2)" stroke="rgba(240,136,62,0.5)" />
              {Array.from({ length: 8 }).map((_, i) => (
                <rect key={i} x={12 + (i % 4) * 28} y={i < 4 ? 2 : 108} width="8" height="8" fill="#58a6ff" rx="1" />
              ))}
            </svg>
            <div>
              <strong>GDSII ready</strong>
              <p>
                {results?.artifacts.find((a) => a.name === "6_final.gds" && a.exists)
                  ? `${(results.artifacts.find((a) => a.name === "6_final.gds")!.size / (1024 * 1024)).toFixed(2)} MB`
                  : "Esegui finish"}
              </p>
            </div>
          </div>
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
        <div className="fl-vis-body fl-vis-pdn">
          <svg viewBox="0 0 320 160" className="fl-vis-pdn-svg" aria-label="Chip PDN straps">
            <rect width="320" height="160" rx="8" fill="#0a0e14" />
            {Array.from({ length: 8 }).map((_, i) => (
              <rect
                key={`h${i}`}
                x="16"
                y={20 + i * 16}
                width="288"
                height="4"
                fill={i % 2 === 0 ? "rgba(248,81,73,0.55)" : "rgba(88,166,255,0.45)"}
                rx="1"
              />
            ))}
            {Array.from({ length: 10 }).map((_, i) => (
              <rect
                key={`v${i}`}
                x={24 + i * 28}
                y="16"
                width="5"
                height="128"
                fill={i % 2 === 0 ? "rgba(248,81,73,0.35)" : "rgba(88,166,255,0.3)"}
                rx="1"
              />
            ))}
            <text x="160" y="150" textAnchor="middle" fill="#8b949e" fontSize="9">
              VDD / VSS straps · check_power_grid
            </text>
          </svg>
          <div className="fl-vis-stat-grid">
            <div className="fl-vis-stat">
              <span>ODB PDN</span>
              <strong className={stageDone ? "ok" : ""}>
                {inspect?.odb ? "OK" : stageDone ? "verificato" : "—"}
              </strong>
            </div>
            <div className="fl-vis-stat">
              <span>Istanze</span>
              <strong>{inspect?.odb?.instances ?? "—"}</strong>
            </div>
            <div className="fl-vis-stat">
              <span>Gridcheck</span>
              <strong className={stageDone ? "ok" : ""}>
                {stageDone ? "PSM-0040" : "Esegui"}
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
              Mesh export · <code>learn/sim/spice/</code> · chip IR post-finish
            </p>
          ) : (
            <p className="fl-vis-meta">
              Dopo finish: chip IR → <code>write_pg_spice</code> · docs mesh SPICE
            </p>
          )}
        </div>
      )}

      {phaseId === "pkg" && (
        <div className="fl-vis-body fl-vis-pkg">
          <svg viewBox="0 0 320 150" className="fl-vis-pkg-svg" aria-label="System PDN stack">
            <rect width="320" height="150" rx="8" fill="#0a0e14" />
            <rect x="40" y="16" width="240" height="22" rx="4" fill="rgba(88,166,255,0.35)" stroke="#58a6ff" />
            <text x="160" y="31" textAnchor="middle" fill="#e6edf3" fontSize="9">
              VRM
            </text>
            <rect x="55" y="44" width="210" height="22" rx="4" fill="rgba(63,185,80,0.3)" stroke="#3fb950" />
            <text x="160" y="59" textAnchor="middle" fill="#e6edf3" fontSize="9">
              Board plane / decap
            </text>
            <rect x="70" y="72" width="180" height="22" rx="4" fill="rgba(240,136,62,0.35)" stroke="#f0883e" />
            <text x="160" y="87" textAnchor="middle" fill="#e6edf3" fontSize="9">
              Package RLC + bumps
            </text>
            <rect x="90" y="100" width="140" height="22" rx="4" fill="rgba(210,153,34,0.3)" stroke="#d29922" />
            <text x="160" y="115" textAnchor="middle" fill="#e6edf3" fontSize="9">
              Die load
            </text>
            <text x="160" y="140" textAnchor="middle" fill="#8b949e" fontSize="8">
              ngspice · Z(f) + load-step
            </text>
          </svg>
          {pdnReport?.impedance || pdnReport?.kind === "system_pdn" ? (
            <>
              <div className="fl-vis-gauge-row">
                <Gauge
                  label="Die droop"
                  value={pdnReport.transient?.droop_mv ?? null}
                  min={0}
                  max={100}
                  unit=" mV"
                  good="low"
                />
                <Gauge
                  label="Zmax"
                  value={pdnReport.impedance?.z_max_mohm ?? null}
                  min={0}
                  max={Math.max(100, (pdnReport.impedance?.z_target_mohm ?? 50) * 4)}
                  unit=" mΩ"
                  good="low"
                />
                <Gauge
                  label="Droop %"
                  value={pdnReport.transient?.droop_pct ?? null}
                  min={0}
                  max={10}
                  unit="%"
                  good="low"
                />
              </div>
              <p className="fl-vis-meta">{pdnReport.summary}</p>
            </>
          ) : pdnReport?.transient?.worst_droop != null ? (
            <>
              <div className="fl-vis-gauge-row">
                <Gauge
                  label="Chip IR droop"
                  value={pdnReport.transient.worst_droop * 1000}
                  min={0}
                  max={100}
                  unit=" mV"
                  good="low"
                />
              </div>
              <p className="fl-vis-meta">
                Report chip IR legacy — rilancia PKG per System PDN gerarchico
              </p>
            </>
          ) : (
            <p className="fl-vis-meta">
              {stageDone
                ? "Report System PDN assente — rilancia PKG"
                : "Esegui PKG: System PDN VRM→board→pkg→die (ngspice)"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

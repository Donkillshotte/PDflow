"use client";

import { useEffect, useRef, useState } from "react";

type VcdData = {
  exists: boolean;
  timescale: string;
  maxTime: number;
  signals: {
    name: string;
    width: number;
    samples: { t: number; v: string }[];
  }[];
};

function valHigh(v: string) {
  if (!v || v === "x" || v === "z") return 0.5;
  if (v.length === 1) return v === "1" ? 1 : 0;
  return parseInt(v, 2) > 0 ? 1 : 0;
}

function sampleAt(samples: { t: number; v: string }[], t: number) {
  if (!samples.length) return "x";
  let v = samples[0]!.v;
  for (const s of samples) {
    if (s.t > t) break;
    v = s.v;
  }
  return v;
}

const COLORS = ["#f0883e", "#58a6ff", "#3fb950", "#d29922", "#f85149", "#a371f7"];

export function RtlWaveformVisual({
  rtlLines,
  sim,
}: {
  rtlLines: number;
  sim: { vcdExists: boolean; logExists: boolean };
}) {
  const [vcd, setVcd] = useState<VcdData | null>(null);
  const [err, setErr] = useState(false);
  const [cursor, setCursor] = useState<number | null>(null);
  const [t0, setT0] = useState(0);
  const [t1, setT1] = useState(1);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!sim.vcdExists) {
      setVcd(null);
      return;
    }
    void fetch("/api/vcd-waveform")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        setVcd(d);
        setErr(!d?.signals?.length);
        if (d?.maxTime) {
          setT0(0);
          setT1(d.maxTime);
        }
      })
      .catch(() => setErr(true));
  }, [sim.vcdExists]);

  const lanes = vcd?.signals ?? [];
  const tMax = vcd?.maxTime || 1;
  const window0 = Math.max(0, Math.min(t0, t1));
  const window1 = Math.max(window0 + 1, Math.max(t0, t1));
  const span = window1 - window0;

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onNativeWheel = (e: WheelEvent) => e.preventDefault();
    el.addEventListener("wheel", onNativeWheel, { passive: false });
    return () => el.removeEventListener("wheel", onNativeWheel);
  }, [lanes.length]);

  const labelW = 92;
  const plotW = 760;
  const laneH = 36;
  const top = 18;
  const height = Math.max(120, lanes.length * laneH + 44);

  const xOf = (t: number) => labelW + ((t - window0) / span) * plotW;
  const tOf = (x: number) => window0 + ((x - labelW) / plotW) * span;

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const svg = e.currentTarget;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return;
    const loc = pt.matrixTransform(ctm.inverse());
    if (loc.x < labelW || loc.x > labelW + plotW) return;
    setCursor(Math.min(window1, Math.max(window0, tOf(loc.x))));
  }

  function onWheel(e: React.WheelEvent<SVGSVGElement>) {
    const mid = cursor ?? (window0 + window1) / 2;
    const factor = e.deltaY > 0 ? 1.18 : 0.84;
    const nextSpan = Math.min(tMax, Math.max(tMax * 0.02, span * factor));
    let n0 = mid - nextSpan / 2;
    let n1 = mid + nextSpan / 2;
    if (n0 < 0) {
      n1 -= n0;
      n0 = 0;
    }
    if (n1 > tMax) {
      n0 -= n1 - tMax;
      n1 = tMax;
    }
    setT0(Math.max(0, n0));
    setT1(Math.min(tMax, n1));
  }

  const ticks = 6;
  const ns = (t: number) => `${(t / 1000).toFixed(tMax > 50_000 ? 0 : 1)} ns`;

  return (
    <div className="fl-vis-rtl fl-wave-studio">
      <div className="fl-vis-stat-grid">
        <div className="fl-vis-stat">
          <span>RTL lines</span>
          <strong>{rtlLines}</strong>
        </div>
        <div className="fl-vis-stat">
          <span>Sim log</span>
          <strong className={sim.logExists ? "ok" : ""}>{sim.logExists ? "OK" : "—"}</strong>
        </div>
        <div className="fl-vis-stat">
          <span>VCD</span>
          <strong className={sim.vcdExists ? "ok" : ""}>{sim.vcdExists ? "Ready" : "—"}</strong>
        </div>
        <div className="fl-vis-stat">
          <span>Cursor</span>
          <strong>{cursor == null ? "—" : ns(cursor)}</strong>
        </div>
      </div>

      {lanes.length > 0 ? (
        <>
          <div className="fl-wave-toolbar">
            <span>
              gcd.vcd · {vcd?.timescale} · window {ns(window0)}–{ns(window1)}
            </span>
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => {
                setT0(0);
                setT1(tMax);
              }}
            >
              Fit time
            </button>
          </div>
          <svg
            ref={svgRef}
            viewBox={`0 0 ${labelW + plotW + 12} ${height}`}
            className="fl-vis-wave fl-vis-wave-real"
            aria-label="VCD waveform"
            onMouseMove={onMove}
            onWheel={onWheel}
          >
            <rect width={labelW + plotW + 12} height={height} rx="8" fill="#070b12" />
            <rect x={labelW} y={8} width={plotW} height={height - 28} fill="#0a1018" />
            {Array.from({ length: ticks + 1 }, (_, i) => {
              const t = window0 + (span * i) / ticks;
              const x = xOf(t);
              return (
                <g key={i}>
                  <line
                    x1={x}
                    y1={8}
                    x2={x}
                    y2={height - 20}
                    stroke="rgba(255,255,255,0.05)"
                  />
                  <text x={x} y={height - 6} textAnchor="middle" fill="#6e7681" fontSize="8">
                    {ns(t)}
                  </text>
                </g>
              );
            })}
            {lanes.map((sig, li) => {
              const color = COLORS[li % COLORS.length]!;
              const yBase = top + li * laneH;
              const yFor = (v: number) => yBase + (1 - v) * (laneH - 12) + 6;
              const pts: string[] = [];
              let lastV = valHigh(sig.samples[0]?.v ?? "0");
              pts.push(`${xOf(window0)},${yFor(lastV)}`);
              for (const s of sig.samples) {
                if (s.t < window0) {
                  lastV = valHigh(s.v);
                  continue;
                }
                if (s.t > window1) break;
                const x = xOf(s.t);
                const hi = valHigh(s.v);
                pts.push(`${x},${yFor(lastV)}`);
                pts.push(`${x},${yFor(hi)}`);
                lastV = hi;
              }
              pts.push(`${xOf(window1)},${yFor(lastV)}`);
              const at = cursor != null ? sampleAt(sig.samples, cursor) : "";
              return (
                <g key={sig.name}>
                  <rect
                    x="0"
                    y={yBase}
                    width={labelW - 4}
                    height={laneH}
                    fill={li % 2 ? "rgba(255,255,255,0.02)" : "transparent"}
                  />
                  <text
                    x="8"
                    y={yBase + 18}
                    fill="#c9d1d9"
                    fontSize="10"
                    fontFamily="ui-monospace, monospace"
                  >
                    {sig.name}
                  </text>
                  <text
                    x={labelW - 8}
                    y={yBase + 18}
                    textAnchor="end"
                    fill={color}
                    fontSize="9"
                    fontFamily="ui-monospace, monospace"
                  >
                    {at}
                  </text>
                  <polyline
                    fill="none"
                    stroke={color}
                    strokeWidth="1.6"
                    points={pts.join(" ")}
                    strokeLinejoin="miter"
                  />
                </g>
              );
            })}
            {cursor != null && (
              <line
                x1={xOf(cursor)}
                y1={8}
                x2={xOf(cursor)}
                y2={height - 20}
                stroke="#f0883e"
                strokeDasharray="3 3"
                strokeWidth="1"
              />
            )}
          </svg>
          <p className="fl-wave-hint">
            Hover for cursor · wheel for time zoom · handshakes (`req_val` /
            `resp_val`) must toggle after reset.
          </p>
        </>
      ) : (
        <svg viewBox="0 0 400 80" className="fl-vis-wave" aria-label="Waveform placeholder">
          <rect width="400" height="80" rx="8" fill="#0a0e14" />
          <text x="200" y="44" textAnchor="middle" fill="#484f58" fontSize="9">
            {sim.vcdExists
              ? err
                ? "VCD present but parsing failed"
                : "Loading waveform…"
              : "Run rtl_sim to generate gcd.vcd"}
          </text>
        </svg>
      )}
    </div>
  );
}

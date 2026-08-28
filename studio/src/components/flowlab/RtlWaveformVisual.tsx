"use client";

import { useEffect, useState } from "react";

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

export function RtlWaveformVisual({
  rtlLines,
  sim,
}: {
  rtlLines: number;
  sim: { vcdExists: boolean; logExists: boolean };
}) {
  const [vcd, setVcd] = useState<VcdData | null>(null);
  const [err, setErr] = useState(false);

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
      })
      .catch(() => setErr(true));
  }, [sim.vcdExists]);

  const width = 480;
  const laneH = 28;
  const lanes = vcd?.signals ?? [];
  const height = Math.max(80, lanes.length * laneH + 36);
  const tMax = vcd?.maxTime || 1;

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
      {lanes.length > 0 ? (
        <svg viewBox={`0 0 ${width} ${height}`} className="fl-vis-wave fl-vis-wave-real" aria-label="VCD waveform">
          <rect width={width} height={height} rx="8" fill="#0a0e14" />
          {lanes.map((sig, li) => {
            const y0 = 16 + li * laneH;
            const color = ["#f0883e", "#58a6ff", "#3fb950", "#d29922", "#f85149", "#a371f7"][li % 6];
            const pts: string[] = [];
            let lastV = 0;
            for (const s of sig.samples) {
              const x = 8 + (s.t / tMax) * (width - 16);
              const hi = valHigh(s.v);
              pts.push(`${x},${y0 + (1 - lastV) * (laneH - 8)}`);
              pts.push(`${x},${y0 + (1 - hi) * (laneH - 8)}`);
              lastV = hi;
            }
            if (pts.length < 2 && sig.samples[0]) {
              const hi = valHigh(sig.samples[0].v);
              pts.push(`8,${y0 + (1 - hi) * (laneH - 8)}`, `${width - 8},${y0 + (1 - hi) * (laneH - 8)}`);
            }
            return (
              <g key={sig.name}>
                <text x="8" y={y0 - 4} fill="#8b949e" fontSize="8" fontFamily="monospace">
                  {sig.name}
                </text>
                <polyline fill="none" stroke={color} strokeWidth="1.5" points={pts.join(" ")} />
              </g>
            );
          })}
          <text x={width / 2} y={height - 6} textAnchor="middle" fill="#484f58" fontSize="8">
            gcd.vcd · {vcd?.timescale} · fino a {(tMax / 1000).toFixed(0)} ns
          </text>
        </svg>
      ) : (
        <svg viewBox="0 0 400 80" className="fl-vis-wave" aria-label="Waveform placeholder">
          <rect width="400" height="80" rx="8" fill="#0a0e14" />
          <text x="200" y="44" textAnchor="middle" fill="#484f58" fontSize="9">
            {sim.vcdExists
              ? err
                ? "VCD presente ma parsing fallito"
                : "Caricamento waveform…"
              : "Esegui rtl_sim per generare gcd.vcd"}
          </text>
        </svg>
      )}
    </div>
  );
}

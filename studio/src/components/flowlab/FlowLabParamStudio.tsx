"use client";

import clsx from "clsx";
import { Gauge, SlidersHorizontal, Zap } from "lucide-react";
import type { FlowlabParams } from "./types";
import { PARAM_PRESETS } from "./types";

function SliderField({
  label,
  hint,
  value,
  display,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  display: string;
  min: number;
  max: number;
  step: number;
  onChange: (n: number) => void;
}) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className="fl-param-card">
      <div className="fl-param-head">
        <div>
          <strong>{label}</strong>
          <p>{hint}</p>
        </div>
        <span className="fl-param-value">{display}</span>
      </div>
      <div className="fl-slider-track">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ "--pct": `${pct}%` } as React.CSSProperties}
        />
      </div>
    </div>
  );
}

export function FlowLabParamStudio({
  params,
  onChange,
  onApplyPreset,
}: {
  params: FlowlabParams;
  onChange: <K extends keyof FlowlabParams>(key: K, value: FlowlabParams[K]) => void;
  onApplyPreset: (key: string) => void;
}) {
  return (
    <div className="fl-param-studio">
      <div className="fl-preset-row">
        <span className="fl-preset-label">
          <SlidersHorizontal size={16} aria-hidden />
          Quick profiles
        </span>
        <div className="fl-preset-chips">
          {Object.entries(PARAM_PRESETS).map(([key, preset]) => (
            <button
              key={key}
              type="button"
              className="fl-preset-chip"
              onClick={() => onApplyPreset(key)}
              title={preset.desc}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <div className="fl-param-grid">
        <div className="fl-param-card fl-param-card-select">
          <div className="fl-param-head">
            <div>
              <strong>SDC · periodo clock</strong>
              <p>Timing constraints applied in synthesis and STA.</p>
            </div>
            <Zap size={18} className="fl-param-icon" aria-hidden />
          </div>
          <select
            value={params.sdcPreset}
            onChange={(e) =>
              onChange("sdcPreset", e.target.value as FlowlabParams["sdcPreset"])
            }
          >
            <option value="default">Default · 0.46 ns (course)</option>
            <option value="relaxed">Relaxed · 2.0 ns (facile)</option>
            <option value="tight">Tight · 0.25 ns (stress)</option>
          </select>
        </div>

        <div className="fl-param-card fl-param-card-select">
          <div className="fl-param-head">
            <div>
              <strong>ABC area / delay</strong>
              <p>Trade-off mappatura logica in Yosys ABC.</p>
            </div>
            <Gauge size={18} className="fl-param-icon" aria-hidden />
          </div>
          <div className="fl-toggle-row">
            {(
              [
                [1, "Area", "Minimize cells"],
                [0, "Delay", "Minimizza path"],
              ] as const
            ).map(([v, title, sub]) => (
              <button
                key={v}
                type="button"
                className={clsx("fl-toggle", params.abcArea === v && "fl-toggle-on")}
                onClick={() => onChange("abcArea", v)}
              >
                <strong>{title}</strong>
                <span>{sub}</span>
              </button>
            ))}
          </div>
        </div>

        <SliderField
          label="Core utilization"
          hint="Percentage of die occupied — higher = smaller chip."
          value={params.coreUtilization}
          display={`${params.coreUtilization}%`}
          min={20}
          max={55}
          step={1}
          onChange={(n) => onChange("coreUtilization", n)}
        />

        <SliderField
          label="Place density addon"
          hint="Extra space between placement rows."
          value={params.placeDensityAddon}
          display={params.placeDensityAddon.toFixed(2)}
          min={0.05}
          max={0.4}
          step={0.01}
          onChange={(n) => onChange("placeDensityAddon", n)}
        />

        <SliderField
          label="TNS end percent"
          hint="How much recovery timing to run post-CTS."
          value={params.tnsEndPercent}
          display={`${params.tnsEndPercent}%`}
          min={0}
          max={100}
          step={5}
          onChange={(n) => onChange("tnsEndPercent", n)}
        />
      </div>

      <div className="fl-make-preview">
        <span>Override ORFS</span>
        <code>
          FLOW_VARIANT=flowlab · CORE_UTILIZATION={params.coreUtilization} · SDC=
          {params.sdcPreset} · ABC_AREA={params.abcArea} · TNS=
          {params.tnsEndPercent}%
        </code>
      </div>
    </div>
  );
}

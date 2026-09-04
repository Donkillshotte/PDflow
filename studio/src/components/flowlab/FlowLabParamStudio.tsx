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
  disabled,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  display: string;
  min: number;
  max: number;
  step: number;
  disabled?: boolean;
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
          disabled={disabled}
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
  locked = false,
}: {
  params: FlowlabParams;
  onChange: <K extends keyof FlowlabParams>(key: K, value: FlowlabParams[K]) => void;
  onApplyPreset: (key: string) => void;
  locked?: boolean;
}) {
  return (
    <div className={clsx("fl-param-studio", locked && "is-locked")}>
      {locked ? (
        <p className="fl-param-locked" role="status">
          flowlab finish is locked — knobs are display-only. Recook would overwrite{" "}
          <code>gcd/flowlab</code>.
        </p>
      ) : null}
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
              disabled={locked}
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
              <strong>SDC · clock period</strong>
              <p>Timing constraints applied in synthesis and STA.</p>
            </div>
            <Zap size={18} className="fl-param-icon" aria-hidden />
          </div>
          <select
            value={params.sdcPreset}
            disabled={locked}
            onChange={(e) =>
              onChange("sdcPreset", e.target.value as FlowlabParams["sdcPreset"])
            }
          >
            <option value="default">Default · 0.46 ns (course)</option>
            <option value="relaxed">Relaxed · 2.0 ns (easy)</option>
            <option value="tight">Tight · 0.25 ns (stress)</option>
          </select>
        </div>

        <div className="fl-param-card fl-param-card-select">
          <div className="fl-param-head">
            <div>
              <strong>ABC area / delay</strong>
              <p>Logic mapping trade-off in Yosys ABC.</p>
            </div>
            <Gauge size={18} className="fl-param-icon" aria-hidden />
          </div>
          <div className="fl-toggle-row">
            {(
              [
                [1, "Area", "Minimize cells"],
                [0, "Delay", "Minimize path delay"],
              ] as const
            ).map(([v, title, sub]) => (
              <button
                key={v}
                type="button"
                className={clsx("fl-toggle", params.abcArea === v && "fl-toggle-on")}
                disabled={locked}
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
          disabled={locked}
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
          disabled={locked}
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
          disabled={locked}
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

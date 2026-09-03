export type FlowlabParams = {
  coreUtilization: number;
  placeDensityAddon: number;
  abcArea: 0 | 1;
  sdcPreset: "default" | "relaxed" | "tight";
  tnsEndPercent: number;
};

export type Phase = {
  id: string;
  label: string;
  title: string;
  action: string;
  hint: string;
  help: string;
  tool: string;
  icon: string;
  estTime: string;
};

export type StageStatus = {
  id: string;
  label: string;
  action: string;
  done: boolean;
  primary?: string;
};

export type RightTab = "log" | "artifacts" | "inspect";

export type StreamEvent =
  | { type: "start"; jobId: string; command: string; action: string }
  | { type: "stdout"; chunk: string }
  | { type: "stderr"; chunk: string }
  | { type: "done"; ok: boolean; code: number | null; ms: number }
  | { type: "error"; message: string }
  | { type: "blocked"; code: string; message: string };

export const PARAM_PRESETS: Record<
  string,
  { label: string; desc: string; params: FlowlabParams }
> = {
  didactic: {
    label: "Tutorial",
    desc: "Relaxed SDC, lower utilization. Fewer congestion failures on the GCD tutorial.",
    params: {
      coreUtilization: 30,
      placeDensityAddon: 0.28,
      abcArea: 1,
      sdcPreset: "relaxed",
      tnsEndPercent: 80,
    },
  },
  balanced: {
    label: "Balanced",
    desc: "Course preset: good area/timing tradeoff for GCD tutorial.",
    params: {
      coreUtilization: 35,
      placeDensityAddon: 0.2,
      abcArea: 1,
      sdcPreset: "default",
      tnsEndPercent: 100,
    },
  },
  aggressive: {
    label: "Aggressive",
    desc: "Tight timing and dense core — higher DRC/congestion risk.",
    params: {
      coreUtilization: 48,
      placeDensityAddon: 0.12,
      abcArea: 0,
      sdcPreset: "tight",
      tnsEndPercent: 100,
    },
  },
};

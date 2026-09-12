/**
 * Pure System PDN report normalization shared by the visualizer and the
 * scenario simulator. Keeping this module free of React components avoids a
 * circular import between the report view and the experiment controls.
 */

export const SERIES = [
  { key: "vrm_v", label: "VRM", node: "vrm", color: "#68c7ff" },
  { key: "board_v", label: "Board", node: "board", color: "#53d487" },
  { key: "package_v", label: "Package", node: "package", color: "#e5b85c" },
  { key: "die_v", label: "Die", node: "die", color: "#ff8b65" },
] as const;

export type SeriesKey = (typeof SERIES)[number]["key"];
type RecordValue = Record<string, unknown>;

export type WavePoint = {
  t: number;
  values: Partial<Record<SeriesKey, number>>;
};

export type CurvePoint = {
  f: number;
  z: number;
  phase: number | null;
};

export type DomainMetric = {
  label: string;
  key: string;
  baseline: number | null;
  minimum: number | null;
  droopMv: number | null;
  droopPct: number | null;
  settled: boolean | null;
};

export type PathDrop = { label: string; valueMv: number };

export type NormalizedReport = {
  status: string;
  ok: boolean | null;
  evidenceOk: boolean | null;
  evidenceClass: string;
  productSignoff: boolean | null;
  vdd: number | null;
  iAvgMa: number | null;
  droopMv: number | null;
  droopPct: number | null;
  peakAtNs: number | null;
  settlingNs: number | null;
  zMaxMOhm: number | null;
  fAtZMax: number | null;
  zTargetMOhm: number | null;
  zConfiguredMOhm: number | null;
  zDerivedMOhm: number | null;
  targetPass: boolean | null;
  wave: WavePoint[];
  curve: CurvePoint[];
  peaks: CurvePoint[];
  domains: DomainMetric[];
  pathDrops: PathDrop[];
  delayNs: number | null;
  pulseWidthNs: number | null;
  runId: string;
  meshId: string;
  variant: string;
  generatedAt: string;
  currentSource: string;
  summary: string;
  inputCount: number;
};

function asRecord(value: unknown): RecordValue | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as RecordValue)
    : null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function readNumber(record: RecordValue | null, key: string): number | null {
  return asNumber(record?.[key]);
}

function readBoolean(record: RecordValue | null, key: string): boolean | null {
  const value = record?.[key];
  return typeof value === "boolean" ? value : null;
}

function firstNumber(...values: unknown[]): number | null {
  for (const value of values) {
    const number = asNumber(value);
    if (number !== null) return number;
  }
  return null;
}

function firstBoolean(...values: unknown[]): boolean | null {
  for (const value of values) {
    if (typeof value === "boolean") return value;
  }
  return null;
}

function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function loadStep(transient: RecordValue | null, root: RecordValue): RecordValue | null {
  return asRecord(root.load_step) ?? asRecord(transient?.load_step);
}

export function normalizeReport(value: unknown): NormalizedReport | null {
  const root = asRecord(value);
  if (!root) return null;

  const transient = asRecord(root.transient);
  const impedance = asRecord(root.impedance);
  const target = asRecord(root.target_impedance);
  const nodes = asRecord(transient?.nodes);
  const rawWave = Array.isArray(transient?.wave) ? transient.wave : [];
  const rawDieWave = Array.isArray(transient?.wave_die) ? transient.wave_die : [];
  const rawCurve = Array.isArray(impedance?.curve) ? impedance.curve : [];
  const rawPeaks = Array.isArray(impedance?.resonance_peaks)
    ? impedance.resonance_peaks
    : [];

  const wave: WavePoint[] = rawWave
    .map((raw) => {
      const point = asRecord(raw);
      const t = readNumber(point, "t_s");
      if (t === null) return null;
      const values: Partial<Record<SeriesKey, number>> = {};
      for (const series of SERIES) {
        const valueAtNode = readNumber(point, series.key);
        if (valueAtNode !== null) values[series.key] = valueAtNode;
      }
      return { t, values };
    })
    .filter((point): point is WavePoint => point !== null)
    .sort((a, b) => a.t - b.t);

  if (!wave.length && rawDieWave.length) {
    for (const raw of rawDieWave) {
      const point = asRecord(raw);
      const t = readNumber(point, "t_s");
      const die = readNumber(point, "v");
      if (t !== null && die !== null) wave.push({ t, values: { die_v: die } });
    }
    wave.sort((a, b) => a.t - b.t);
  }

  const curve: CurvePoint[] = rawCurve
    .map((raw) => {
      const point = asRecord(raw);
      const f = readNumber(point, "f_hz");
      const zMOhm = firstNumber(
        point && point.z_mohm,
        readNumber(point, "z_ohm") === null
          ? null
          : (readNumber(point, "z_ohm") as number) * 1000,
      );
      if (f === null || zMOhm === null || f <= 0 || zMOhm <= 0) return null;
      return { f, z: zMOhm, phase: readNumber(point, "phase_deg") };
    })
    .filter((point): point is CurvePoint => point !== null)
    .sort((a, b) => a.f - b.f);

  const peaks: CurvePoint[] = rawPeaks
    .map<CurvePoint | null>((raw): CurvePoint | null => {
      const point = asRecord(raw);
      const f = readNumber(point, "f_hz");
      const zMOhm = firstNumber(
        point && point.z_mohm,
        readNumber(point, "z_ohm") === null
          ? null
          : (readNumber(point, "z_ohm") as number) * 1000,
      );
      if (f === null || zMOhm === null || f <= 0 || zMOhm <= 0) return null;
      return { f, z: zMOhm, phase: null as number | null };
    })
    .filter((point): point is CurvePoint => point !== null)
    .sort((a, b) => b.z - a.z);

  const domainKeys = new Set(SERIES.map((series) => series.node));
  const domains: DomainMetric[] = SERIES.map((series) => {
    const node = asRecord(nodes?.[series.node]);
    const values = wave
      .map((point) => point.values[series.key])
      .filter((entry): entry is number => entry !== undefined);
    const baseline = firstNumber(readNumber(node, "v_baseline"), values[0]);
    const minimum = firstNumber(
      readNumber(node, "v_min"),
      values.length ? Math.min(...values) : null,
    );
    const derivedDroop =
      baseline !== null && minimum !== null ? (baseline - minimum) * 1000 : null;
    return {
      label: series.label,
      key: series.node,
      baseline,
      minimum,
      droopMv: firstNumber(readNumber(node, "droop_mv"), derivedDroop),
      droopPct: readNumber(node, "droop_pct"),
      settled: readBoolean(node, "settled"),
    };
  }).filter((domain) => domainKeys.has(domain.key));

  const rawDrops = asRecord(transient?.path_drops_at_peak_mv);
  const pathDrops = rawDrops
    ? Object.entries(rawDrops)
        .map(([key, value]) => {
          const number = asNumber(value);
          return number === null
            ? null
            : { label: titleCase(key.replace(/_mv$/, "")), valueMv: number };
        })
        .filter((drop): drop is PathDrop => drop !== null)
    : [];

  const configuredTarget = firstNumber(
    readNumber(impedance, "z_target_mohm"),
    readNumber(target, "configured_z_target_mohm"),
  );
  const derivedTarget = firstNumber(
    readNumber(impedance, "z_target_effective_mohm") === configuredTarget
      ? null
      : readNumber(impedance, "z_target_effective_mohm"),
    readNumber(target, "derived_z_target_mohm"),
  );
  const effectiveTarget = firstNumber(
    readNumber(impedance, "z_target_effective_mohm"),
    configuredTarget,
    derivedTarget,
  );
  const status = String(root.status ?? (root.ok === true ? "PASS" : "NOT_RUN")).toUpperCase();
  const currentSource = asRecord(root.current_source);
  const sourceKind = String(currentSource?.kind ?? "unknown");
  const sourceValue = readNumber(currentSource, "value_a");
  const sourceText =
    sourceValue === null
      ? sourceKind
      : `${sourceKind} · ${(sourceValue * 1000).toLocaleString(undefined, { maximumFractionDigits: 3 })} mA`;

  const loadStepData = loadStep(transient, root);
  const delay = readNumber(loadStepData, "delay_s");
  const pulseWidth = readNumber(loadStepData, "pulse_width_s");

  return {
    status,
    ok: firstBoolean(root.ok),
    evidenceOk: firstBoolean(root.evidence_ok),
    evidenceClass: String(root.evidence_class ?? "UNKNOWN"),
    productSignoff: firstBoolean(root.product_signoff),
    vdd: readNumber(root, "vdd"),
    iAvgMa: readNumber(root, "i_die_avg_a") === null ? null : (readNumber(root, "i_die_avg_a") as number) * 1000,
    droopMv: readNumber(transient, "droop_mv"),
    droopPct: readNumber(transient, "droop_pct"),
    peakAtNs: readNumber(transient, "peak_at_s") === null ? null : (readNumber(transient, "peak_at_s") as number) * 1e9,
    settlingNs:
      readNumber(transient, "settling_time_s") === null
        ? null
        : (readNumber(transient, "settling_time_s") as number) * 1e9,
    zMaxMOhm: firstNumber(
      readNumber(impedance, "z_max_mohm"),
      curve.length ? Math.max(...curve.map((point) => point.z)) : null,
    ),
    fAtZMax: readNumber(impedance, "f_at_zmax_hz"),
    zTargetMOhm: effectiveTarget,
    zConfiguredMOhm: configuredTarget,
    zDerivedMOhm: derivedTarget,
    targetPass: firstBoolean(
      impedance?.pass_target_effective,
      impedance?.pass_target,
      target?.configured_pass,
      target?.derived_pass,
    ),
    wave,
    curve,
    peaks,
    domains,
    pathDrops,
    delayNs: delay === null ? null : delay * 1e9,
    pulseWidthNs: pulseWidth === null ? null : pulseWidth * 1e9,
    runId: String(root.run_id ?? root.analysis_id ?? "not available"),
    meshId: String(root.mesh_id ?? "not available"),
    variant: String(root.variant ?? "unknown"),
    generatedAt: String(root.generated_at ?? "not available"),
    currentSource: sourceText,
    summary: String(root.summary ?? "System PDN report loaded."),
    inputCount: Array.isArray(root.input_artifacts) ? root.input_artifacts.length : 0,
  };
}

"use client";

import { Play, Square } from "lucide-react";
import { useEffect, useState } from "react";
import {
  normalizeReport,
  type NormalizedReport,
} from "./systemPdnReport";
import styles from "./SystemPdnVisual.module.css";

export type SystemPdnScenarioControls = {
  die_current_ma: number;
  peak_factor: number;
  board_l_nh: number;
  package_r_mohm: number;
  package_l_nh: number;
  board_bulk_uf: number;
  package_c_pf: number;
  target_z_mohm: number;
  edge_ns: number;
  delay_ns: number;
  pulse_width_ns: number;
};

type ScenarioJob = {
  job_id: string;
  state: string;
  reason?: string | null;
  report?: { status?: string; ok?: boolean } | null;
};

type ScenarioProgressState = "PREPARING" | "QUEUED" | "RUNNING" | "READING";

type SweepKey =
  | "peak_factor"
  | "package_r_mohm"
  | "package_l_nh"
  | "board_bulk_uf";

type SweepRowState = "PENDING" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";

type SweepRow = {
  id: string;
  scale: number;
  value: number;
  controls: SystemPdnScenarioControls;
  state: SweepRowState;
  runId: string | null;
  report: NormalizedReport | null;
  raw: unknown | null;
  error: string | null;
};

type ScenarioExecution = {
  runId: string;
  raw: unknown;
};

type ScenarioProgressCallback = (
  state: ScenarioProgressState,
  job?: ScenarioJob,
) => void;

type SimulatorProps = {
  variant: string;
  baseline: NormalizedReport | null;
  scenario: NormalizedReport | null;
  scenarioRunId: string | null;
  activeView: "baseline" | "scenario";
  onScenarioLoaded: (
    raw: unknown,
    runId: string,
    controls: SystemPdnScenarioControls,
  ) => boolean;
  onSelectView: (view: "baseline" | "scenario") => void;
};

const DEFAULT_CONTROLS: SystemPdnScenarioControls = {
  die_current_ma: 0.72,
  peak_factor: 4,
  board_l_nh: 1,
  package_r_mohm: 40,
  package_l_nh: 0.3,
  board_bulk_uf: 22,
  package_c_pf: 200,
  target_z_mohm: 50,
  edge_ns: 2,
  delay_ns: 20,
  pulse_width_ns: 80,
};

type ControlKey = keyof SystemPdnScenarioControls;

const ELECTRICAL_FIELDS: Array<{
  key: ControlKey;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number;
}> = [
  { key: "die_current_ma", label: "Die current", unit: "mA", min: 0.01, max: 20, step: 0.01 },
  { key: "peak_factor", label: "Load peak factor", unit: "× Iavg", min: 1, max: 16, step: 0.1 },
  { key: "board_l_nh", label: "Board plane L", unit: "nH", min: 0.01, max: 20, step: 0.01 },
  { key: "package_r_mohm", label: "Package path R", unit: "mΩ", min: 0.01, max: 500, step: 0.1 },
  { key: "package_l_nh", label: "Package path L", unit: "nH", min: 0.001, max: 20, step: 0.001 },
  { key: "board_bulk_uf", label: "Board bulk C", unit: "µF", min: 0.1, max: 2000, step: 0.1 },
  { key: "package_c_pf", label: "Package C", unit: "pF", min: 1, max: 10000, step: 1 },
  { key: "target_z_mohm", label: "Target |Z|", unit: "mΩ", min: 0.1, max: 2000, step: 0.1 },
];

const TIMING_FIELDS: Array<{
  key: ControlKey;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number;
}> = [
  { key: "edge_ns", label: "Edge", unit: "ns", min: 0.05, max: 50, step: 0.05 },
  { key: "delay_ns", label: "Load delay", unit: "ns", min: 0, max: 1000, step: 0.1 },
  { key: "pulse_width_ns", label: "Pulse width", unit: "ns", min: 0.1, max: 1000, step: 0.1 },
];

const SWEEP_KEYS: readonly SweepKey[] = [
  "peak_factor",
  "package_r_mohm",
  "package_l_nh",
  "board_bulk_uf",
];

const SWEEP_FIELDS = SWEEP_KEYS.map((key) =>
  ELECTRICAL_FIELDS.find((field) => field.key === key),
).filter((field): field is (typeof ELECTRICAL_FIELDS)[number] => Boolean(field));

function format(value: number | null, digits = 3): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function delta(value: number | null, baseline: number | null, unit: string): string {
  if (value === null || baseline === null) return "—";
  const difference = value - baseline;
  const sign = difference > 0 ? "+" : "";
  return `${sign}${format(difference, 3)} ${unit}`;
}

function deltaClass(value: number | null, baseline: number | null): string {
  if (value === null || baseline === null || value === baseline) return styles.simDeltaNeutral;
  return value < baseline ? styles.simDeltaGood : styles.simDeltaBad;
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function errorText(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const value = (body as { error?: unknown }).error;
    if (typeof value === "string" && value) return value;
  }
  return fallback;
}

function validateControls(value: SystemPdnScenarioControls): string | null {
  const invalid = Object.entries(value).find(([, control]) => !Number.isFinite(control));
  return invalid?.[0] ?? null;
}

function roundSweepValue(value: number, step: number): number {
  const decimals = Math.max(3, (String(step).split(".")[1] ?? "").length);
  return Number(value.toFixed(decimals));
}

function makeSweepRows(
  axis: SweepKey,
  baseControls: SystemPdnScenarioControls,
): SweepRow[] {
  const field = ELECTRICAL_FIELDS.find((candidate) => candidate.key === axis);
  if (!field) return [];
  const base = baseControls[axis];
  return [0.5, 1, 2].map((scale) => {
    const value = roundSweepValue(
      Math.min(field.max, Math.max(field.min, base * scale)),
      field.step,
    );
    return {
      id: `${axis}-${scale}`,
      scale,
      value,
      controls: { ...baseControls, [axis]: value },
      state: "PENDING" as const,
      runId: null,
      report: null,
      raw: null,
      error: null,
    };
  });
}

async function executeScenario(
  variant: string,
  controls: SystemPdnScenarioControls,
  onProgress?: ScenarioProgressCallback,
): Promise<ScenarioExecution> {
  onProgress?.("PREPARING");
  const runResponse = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      surface: "package",
      profile: "system-pdn-scenario",
      design_id: "gcd",
      pdk_id: variant.startsWith("lab_asap7_") ? "asap7" : "nangate45",
    }),
  });
  const runBody = (await runResponse.json().catch(() => null)) as {
    run?: { run_id?: string };
    error?: string;
  } | null;
  if (!runResponse.ok || !runBody?.run?.run_id) {
    throw new Error(errorText(runBody, "Could not create the isolated run"));
  }
  const runId = runBody.run.run_id;

  onProgress?.("PREPARING");
  const submitResponse = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: "system_pdn",
      operation: "action",
      variant,
      mode: "view",
      run_id: runId,
      parameters: controls,
    }),
  });
  const submitBody = (await submitResponse.json().catch(() => null)) as ScenarioJob & {
    error?: string;
  };
  if (!submitResponse.ok || !submitBody?.job_id) {
    throw new Error(errorText(submitBody, "System PDN action was rejected"));
  }
  let current: ScenarioJob = submitBody;
  onProgress?.(current.state === "RUNNING" ? "RUNNING" : "QUEUED", current);
  while (current.state === "QUEUED" || current.state === "RUNNING") {
    await sleep(550);
    const statusResponse = await fetch(
      `/api/jobs/${encodeURIComponent(current.job_id)}`,
      { cache: "no-store" },
    );
    const statusBody = (await statusResponse.json().catch(() => null)) as ScenarioJob | null;
    if (!statusResponse.ok || !statusBody) {
      throw new Error("System PDN job status is unavailable");
    }
    current = statusBody;
    onProgress?.(current.state === "RUNNING" ? "RUNNING" : "QUEUED", current);
  }

  if (current.state !== "COMPLETED") {
    throw new Error(current.reason || `System PDN ${current.state.toLowerCase()}`);
  }
  onProgress?.("READING", current);
  const reportResponse = await fetch(
    `/api/system-pdn/report?run_id=${encodeURIComponent(runId)}`,
    { cache: "no-store" },
  );
  const reportBody = await reportResponse.json().catch(() => null);
  if (!reportResponse.ok) {
    throw new Error(errorText(reportBody, "Scenario report is unavailable"));
  }
  return { runId, raw: reportBody };
}

function Field({
  field,
  value,
  onChange,
  disabled = false,
}: {
  field: (typeof ELECTRICAL_FIELDS)[number];
  value: number;
  onChange: (key: ControlKey, value: number) => void;
  disabled?: boolean;
}) {
  return (
    <label className={styles.simField} htmlFor={`system-pdn-${field.key}`}>
      <span>{field.label}</span>
      <div className={styles.simInputWrap}>
        <input
          id={`system-pdn-${field.key}`}
          type="number"
          inputMode="decimal"
          min={field.min}
          max={field.max}
          step={field.step}
          value={Number.isFinite(value) ? value : ""}
          disabled={disabled}
          onChange={(event) => onChange(field.key, Number(event.target.value))}
        />
        <small>{field.unit}</small>
      </div>
    </label>
  );
}

function TimingField({
  field,
  value,
  onChange,
  disabled = false,
}: {
  field: (typeof TIMING_FIELDS)[number];
  value: number;
  onChange: (key: ControlKey, value: number) => void;
  disabled?: boolean;
}) {
  return (
    <label className={styles.simField} htmlFor={`system-pdn-${field.key}`}>
      <span>{field.label}</span>
      <div className={styles.simInputWrap}>
        <input
          id={`system-pdn-${field.key}`}
          type="number"
          inputMode="decimal"
          min={field.min}
          max={field.max}
          step={field.step}
          value={Number.isFinite(value) ? value : ""}
          disabled={disabled}
          onChange={(event) => onChange(field.key, Number(event.target.value))}
        />
        <small>{field.unit}</small>
      </div>
    </label>
  );
}

export function SystemPdnSimulator({
  variant,
  baseline,
  scenario,
  scenarioRunId,
  activeView,
  onScenarioLoaded,
  onSelectView,
}: SimulatorProps) {
  const [controls, setControls] = useState<SystemPdnScenarioControls>(DEFAULT_CONTROLS);
  const [controlsTouched, setControlsTouched] = useState(false);
  const [job, setJob] = useState<ScenarioJob | null>(null);
  const [running, setRunning] = useState(false);
  const [sweepAxis, setSweepAxis] = useState<SweepKey>("package_r_mohm");
  const [sweepRows, setSweepRows] = useState<SweepRow[]>([]);
  const [sweepRunning, setSweepRunning] = useState(false);
  const [sweepMessage, setSweepMessage] = useState<string | null>(null);
  const [message, setMessage] = useState("Ready — this will create an isolated ngspice run.");

  useEffect(() => {
    if (controlsTouched || !baseline) return;
    setControls((current) => ({
      ...current,
      die_current_ma: baseline.iAvgMa ?? current.die_current_ma,
      target_z_mohm: baseline.zConfiguredMOhm ?? current.target_z_mohm,
    }));
  }, [baseline, controlsTouched]);

  function updateControl(key: ControlKey, value: number) {
    setControlsTouched(true);
    setControls((current) => ({ ...current, [key]: value }));
  }

  async function runScenario() {
    if (running || sweepRunning) return;
    const invalid = validateControls(controls);
    if (invalid) {
      setMessage(`Invalid value for ${invalid}`);
      return;
    }

    setRunning(true);
    setSweepRows([]);
    setSweepMessage(null);
    setJob(null);
    try {
      const execution = await executeScenario(variant, controls, (state, nextJob) => {
        setJob(nextJob ?? null);
        if (state === "PREPARING") setMessage("Creating isolated Package run…");
        if (state === "QUEUED") setMessage("Queued behind the native resource guard…");
        if (state === "RUNNING") setMessage("ngspice is solving TRAN + AC…");
        if (state === "READING") setMessage("Reading the isolated report and waveform…");
      });
      if (!onScenarioLoaded(execution.raw, execution.runId, controls)) {
        throw new Error("Scenario report is not a valid System PDN report");
      }
      setMessage(`Scenario ready · ${execution.runId} · report and netlists are isolated.`);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "System PDN scenario failed");
    } finally {
      setRunning(false);
    }
  }

  async function runSweep() {
    if (running || sweepRunning) return;
    const invalid = validateControls(controls);
    if (invalid) {
      setSweepMessage(`Invalid value for ${invalid}`);
      return;
    }
    const rows = makeSweepRows(sweepAxis, controls);
    const field = SWEEP_FIELDS.find((candidate) => candidate.key === sweepAxis);
    if (!rows.length || !field) {
      setSweepMessage("Select a valid electrical sweep axis");
      return;
    }

    setSweepRows(rows);
    setSweepRunning(true);
    setJob(null);
    setSweepMessage(`0/${rows.length} points complete · sequential native runs`);
    let completed = 0;

    try {
      for (let index = 0; index < rows.length; index += 1) {
        const row = rows[index];
        setSweepRows((current) => current.map((item) => (
          item.id === row.id ? { ...item, state: "PENDING", error: null } : item
        )));
        setMessage(`Sweep ${index + 1}/${rows.length} · ${field.label} ${format(row.value, 3)} ${field.unit}`);

        try {
          const execution = await executeScenario(variant, row.controls, (state, nextJob) => {
            setJob(nextJob ?? null);
            const rowState: SweepRowState = state === "QUEUED"
              ? "QUEUED"
              : state === "RUNNING" || state === "READING"
                ? "RUNNING"
                : "PENDING";
            setSweepRows((current) => current.map((item) => (
              item.id === row.id ? { ...item, state: rowState, error: null } : item
            )));
            if (state === "QUEUED") setMessage(`Sweep ${index + 1}/${rows.length} · queued behind native resource guard…`);
            if (state === "RUNNING") setMessage(`Sweep ${index + 1}/${rows.length} · ngspice solving TRAN + AC…`);
            if (state === "READING") setMessage(`Sweep ${index + 1}/${rows.length} · reading waveform…`);
          });
          const report = normalizeReport(execution.raw);
          if (!report || !onScenarioLoaded(execution.raw, execution.runId, row.controls)) {
            throw new Error("Scenario report is not a valid System PDN report");
          }
          completed += 1;
          setSweepRows((current) => current.map((item) => (
            item.id === row.id
              ? { ...item, state: "COMPLETED", runId: execution.runId, report, raw: execution.raw, error: null }
              : item
          )));
          setSweepMessage(`${completed}/${rows.length} points complete · last run ${execution.runId}`);
        } catch (cause) {
          const reason = cause instanceof Error ? cause.message : "System PDN sweep point failed";
          setSweepRows((current) => current.map((item) => (
            item.id === row.id ? { ...item, state: "FAILED", error: reason } : item
          )));
          setSweepMessage(`${completed}/${rows.length} points complete · point ${index + 1} failed`);
        }
      }
      setMessage(`Sensitivity sweep complete · ${completed}/${rows.length} native runs completed.`);
      setSweepMessage(`${completed}/${rows.length} points complete · every point has an isolated run`);
    } finally {
      setSweepRunning(false);
      setJob(null);
    }
  }

  async function cancelScenario() {
    if (!job || !running) return;
    await fetch(`/api/jobs/${encodeURIComponent(job.job_id)}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    setMessage("Cancellation requested.");
  }

  function viewSweepRow(row: SweepRow) {
    if (sweepRunning || !row.raw || !row.runId) return;
    if (!onScenarioLoaded(row.raw, row.runId, row.controls)) {
      setSweepMessage("This sweep report is no longer valid");
      return;
    }
    onSelectView("scenario");
    setMessage(`Viewing sweep point · ${row.runId}`);
  }

  const shownScenario = scenario && scenarioRunId ? scenario : null;
  const busy = running || sweepRunning;
  const status = busy ? job?.state || "PREPARING" : shownScenario ? "READY" : "IDLE";
  const sweepField = SWEEP_FIELDS.find((field) => field.key === sweepAxis);

  return (
    <section className={styles.simulator} aria-label="System PDN ngspice simulator">
      <header className={styles.simHeader}>
        <div>
          <span className={styles.kicker}>Experiment surface · native solver</span>
          <h3>Simulate a System PDN scenario</h3>
          <p>
            Change bounded RLC/load controls, then run the real <code>system_pdn</code> agent action. Each result gets its own run, config, netlists, log, and report.
          </p>
        </div>
        <span className={`${styles.status} ${status === "READY" ? styles.statusOk : status === "IDLE" ? styles.statusWarn : styles.statusWarn}`}>
          {status}
        </span>
      </header>

      <div className={styles.simControls}>
        <div className={styles.simSectionTitle}>
          <span>Electrical controls</span>
          <small>engineering units · validated by agent</small>
        </div>
        <div className={styles.simGrid}>
          {ELECTRICAL_FIELDS.map((field) => (
            <Field
              key={field.key}
              field={field}
              value={controls[field.key]}
              disabled={busy}
              onChange={updateControl}
            />
          ))}
        </div>
        <details className={styles.simAdvanced}>
          <summary>Load-step timing</summary>
          <div className={styles.simGrid}>
            {TIMING_FIELDS.map((field) => (
              <TimingField
                key={field.key}
                field={field}
                value={controls[field.key]}
                disabled={busy}
                onChange={updateControl}
              />
            ))}
          </div>
        </details>
      </div>

      <div className={styles.simActions}>
        <button type="button" className={styles.simButtonPrimary} onClick={() => void runScenario()} disabled={busy}>
          <Play size={13} aria-hidden />
          {running ? "Solving…" : sweepRunning ? "Sweep in progress…" : "Run ngspice scenario"}
        </button>
        {running && (
          <button type="button" className={styles.simButton} onClick={() => void cancelScenario()}>
            <Square size={12} aria-hidden /> Cancel
          </button>
        )}
        {shownScenario && (
          <>
            <button
              type="button"
              className={activeView === "scenario" ? styles.simButtonActive : styles.simButton}
              onClick={() => onSelectView("scenario")}
            >
              View scenario
            </button>
            <button
              type="button"
              className={activeView === "baseline" ? styles.simButtonActive : styles.simButton}
              onClick={() => onSelectView("baseline")}
            >
              View baseline
            </button>
          </>
        )}
        <span className={styles.simMessage} role="status">{message}</span>
      </div>

      <section className={styles.simSweep} aria-label="System PDN sensitivity sweep">
        <div className={styles.simSectionTitle}>
          <span>3-point sensitivity</span>
          <small>0.5× / 1× / 2× · one isolated ngspice run per point</small>
        </div>
        <div className={styles.simSweepControls}>
          <label className={styles.simSweepSelect} htmlFor="system-pdn-sweep-axis">
            <span>Sweep axis</span>
            <select
              id="system-pdn-sweep-axis"
              value={sweepAxis}
              onChange={(event) => setSweepAxis(event.target.value as SweepKey)}
              disabled={busy}
            >
              {SWEEP_FIELDS.map((field) => (
                <option key={field.key} value={field.key}>{field.label} ({field.unit})</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className={styles.simButton}
            onClick={() => void runSweep()}
            disabled={busy}
          >
            {sweepRunning ? "Running 3 points…" : "Run 3-point sweep"}
          </button>
          <span className={styles.simSweepHint} role="status">
            {sweepMessage ?? (sweepField ? `Base ${format(controls[sweepField.key], 3)} ${sweepField.unit}` : "")}
          </span>
        </div>

        {sweepRows.length > 0 && sweepField && (
          <div className={styles.simSweepTableWrap}>
            <table className={styles.simSweepTable}>
              <caption className={styles.simSweepCaption}>
                Native System PDN sweep over {sweepField.label}; each row has its own run directory.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Point</th>
                  <th scope="col">{sweepField.label}</th>
                  <th scope="col">Die droop</th>
                  <th scope="col">Zmax</th>
                  <th scope="col">Resonance</th>
                  <th scope="col">State</th>
                  <th scope="col"><span className={styles.visuallyHidden}>Action</span></th>
                </tr>
              </thead>
              <tbody>
                {sweepRows.map((row) => {
                  const rowStatusClass = row.state === "COMPLETED"
                    ? styles.statusOk
                    : row.state === "FAILED"
                      ? styles.statusBad
                      : styles.statusWarn;
                  return (
                    <tr key={row.id}>
                      <th scope="row">{row.scale.toFixed(1)}×</th>
                      <td><code>{format(row.value, 3)} {sweepField.unit}</code></td>
                      <td>{format(row.report?.droopMv ?? null, 3)} mV</td>
                      <td>{format(row.report?.zMaxMOhm ?? null, 2)} mΩ</td>
                      <td>{row.report?.fAtZMax === null || row.report?.fAtZMax === undefined
                        ? "—"
                        : `${format(row.report.fAtZMax / 1e6, 2)} MHz`}</td>
                      <td>
                        <span className={`${styles.simSweepState} ${rowStatusClass}`}>{row.state}</span>
                        {row.error && <small className={styles.simSweepError} title={row.error}>failed</small>}
                      </td>
                      <td>
                        {row.raw && row.runId ? (
                          <button
                            type="button"
                            className={styles.simSweepView}
                            onClick={() => viewSweepRow(row)}
                            disabled={busy}
                          >
                            View
                          </button>
                        ) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {shownScenario && baseline && (
        <div className={styles.simComparison}>
          <div className={styles.simSectionTitle}>
            <span>Scenario delta</span>
            <small>scenario − baseline · {scenarioRunId}</small>
          </div>
          <div className={styles.simDeltaGrid}>
            <div className={styles.simDeltaCard}>
              <span>Die droop</span>
              <strong>{format(shownScenario.droopMv, 3)} mV</strong>
              <small className={deltaClass(shownScenario.droopMv, baseline.droopMv)}>{delta(shownScenario.droopMv, baseline.droopMv, "mV")}</small>
            </div>
            <div className={styles.simDeltaCard}>
              <span>Zmax</span>
              <strong>{format(shownScenario.zMaxMOhm, 2)} mΩ</strong>
              <small className={deltaClass(shownScenario.zMaxMOhm, baseline.zMaxMOhm)}>{delta(shownScenario.zMaxMOhm, baseline.zMaxMOhm, "mΩ")}</small>
            </div>
            <div className={styles.simDeltaCard}>
              <span>Resonance</span>
              <strong>{shownScenario.fAtZMax === null ? "—" : `${format(shownScenario.fAtZMax / 1e6, 2)} MHz`}</strong>
              <small className={styles.simDeltaNeutral}>{delta(shownScenario.fAtZMax, baseline.fAtZMax, "Hz")}</small>
            </div>
            <div className={styles.simDeltaCard}>
              <span>Evidence</span>
              <strong>{shownScenario.status}</strong>
              <small>{shownScenario.wave.length} TRAN · {shownScenario.curve.length} AC points</small>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

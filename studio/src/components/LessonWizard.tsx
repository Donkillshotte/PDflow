"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { MarkdownView } from "@/components/MarkdownView";
import { LessonLayoutPanel } from "@/components/LessonLayoutPanel";
import { LessonPowerChainPanel } from "@/components/LessonPowerChainPanel";
import { LiveRunConsole } from "@/components/LiveRunConsole";
import { ResultsPanel } from "@/components/ResultsPanel";
import { useToast } from "@/components/ToastProvider";

type LessonPayload = {
  id: string;
  num: string;
  title: string;
  duration: string;
  stage: string;
  blurb: string;
  makeTarget: string;
  readme: string | null;
  lab: string | null;
};

type CheckItem = { id: string; label: string };

type Gate = { id: string; label: string; ok: boolean; detail?: string };

const STEPS = [
  { id: "theory", label: "1 · Theory", short: "Theory" },
  { id: "lab", label: "2 · LAB", short: "LAB" },
  { id: "run", label: "3 · Run", short: "Run" },
  { id: "results", label: "4 · Results", short: "Results" },
  { id: "chiudi", label: "5 · Close", short: "Close" },
] as const;

type StepId = (typeof STEPS)[number]["id"];

function extractChecks(lab: string): CheckItem[] {
  const items: CheckItem[] = [];
  const seen = new Set<string>();
  for (const line of lab.split("\n")) {
    const check = line.match(/^- \[[ xX]\]\s+(.+)/);
    const parte = line.match(/^##\s+(Parte\s+\d+[^\n]*)/i);
    const label = (check?.[1] || parte?.[1] || "").trim();
    if (!label || label.length < 4) continue;
    const id = label
      .toLowerCase()
      .replace(/[^a-z0-9àèéìòù]+/gi, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 64);
    if (seen.has(id)) continue;
    seen.add(id);
    items.push({ id, label: label.slice(0, 120) });
    if (items.length >= 12) break;
  }
  return items;
}

export function LessonWizard({ lesson }: { lesson: LessonPayload }) {
  const { push } = useToast();
  const [step, setStep] = useState<StepId>("theory");
  const [doneSteps, setDoneSteps] = useState<string[]>([]);
  const [checks, setChecks] = useState<string[]>([]);
  const [completed, setCompleted] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [gates, setGates] = useState<Gate[]>([]);
  const [gatesOk, setGatesOk] = useState(false);
  const [completeError, setCompleteError] = useState<string | null>(null);

  const checklist = useMemo(
    () => (lesson.lab ? extractChecks(lesson.lab) : []),
    [lesson.lab],
  );

  async function refreshGates() {
    const res = await fetch(`/api/progress?lessonId=${encodeURIComponent(lesson.id)}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.gates) {
      setGates(data.gates.gates ?? []);
      setGatesOk(Boolean(data.gates.ok));
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetch(`/api/progress?lessonId=${encodeURIComponent(lesson.id)}`);
      const data = await res.json();
      if (cancelled) return;
      const p = data.progress ?? data;
      setDoneSteps(p.lesson_steps?.[lesson.id] ?? []);
      setChecks(p.lab_checks?.[lesson.id] ?? []);
      setCompleted((p.completed_lessons ?? []).includes(lesson.id));
      if (data.gates) {
        setGates(data.gates.gates ?? []);
        setGatesOk(Boolean(data.gates.ok));
      }
      const saved = p.lesson_steps?.[lesson.id] as string[] | undefined;
      if (saved?.length) {
        const last = STEPS.map((s) => s.id).filter((id) => saved.includes(id)).pop();
        if (last) setStep(last);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lesson.id]);

  async function persistSteps(next: string[]) {
    setDoneSteps(next);
    setSaving(true);
    await fetch("/api/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lessonId: lesson.id,
        action: "steps",
        steps: next,
      }),
    });
    setSaving(false);
    await refreshGates();
  }

  async function persistChecks(next: string[]) {
    setChecks(next);
    await fetch("/api/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lessonId: lesson.id,
        action: "checks",
        checks: next,
      }),
    });
    await refreshGates();
  }

  function markStep(id: StepId) {
    const next = Array.from(new Set([...doneSteps, id]));
    void persistSteps(next);
  }

  function go(id: StepId) {
    setStep(id);
  }

  function nextStep() {
    const idx = STEPS.findIndex((s) => s.id === step);
    markStep(step);
    if (idx < STEPS.length - 1) setStep(STEPS[idx + 1].id);
  }

  function prevStep() {
    const idx = STEPS.findIndex((s) => s.id === step);
    if (idx > 0) setStep(STEPS[idx - 1].id);
  }

  async function completeLesson() {
    setCompleteError(null);
    markStep("chiudi");
    const res = await fetch("/api/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lessonId: lesson.id }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      setCompleted(true);
      push("Lesson marked as completed", "ok");
      await refreshGates();
      return;
    }
    if (data.gates) {
      setGates(data.gates);
      setGatesOk(false);
    }
    const msg = data.error || "Unable to complete: gates not satisfied";
    setCompleteError(msg);
    push(msg, "bad");
  }

  const stepIndex = STEPS.findIndex((s) => s.id === step);
  const checksDone = checklist.length
    ? checks.filter((c) => checklist.some((i) => i.id === c)).length
    : 0;

  return (
    <div className="wizard">
      <ol className="wizard-steps" aria-label="Lesson steps">
        {STEPS.map((s, i) => {
          const active = s.id === step;
          const done = doneSteps.includes(s.id);
          return (
            <li key={s.id}>
              <button
                type="button"
                className={clsx("wizard-step", active && "active", done && "done")}
                onClick={() => go(s.id)}
                aria-current={active ? "step" : undefined}
              >
                <span className="wizard-idx">{i + 1}</span>
                <span className="wizard-label">{s.short}</span>
              </button>
            </li>
          );
        })}
      </ol>

      <LessonPowerChainPanel lessonId={lesson.id} />

      <div className="wizard-body panel">
        {step === "theory" && (
          <div className="wizard-pane">
            <header className="wizard-pane-head">
              <h2>Read the theory</h2>
              <p>Once you understand this phase contract, move on to the LAB.</p>
            </header>
            {lesson.readme ? (
              <MarkdownView
                content={lesson.readme}
                basePath={`lessons/${lesson.id}`}
              />
            ) : (
              <p className="empty-hint">README missing.</p>
            )}
          </div>
        )}

        {step === "lab" && (
          <div className="wizard-pane">
            <header className="wizard-pane-head">
              <h2>Interactive lab</h2>
              <p>
                Check off parts as you go ({checksDone}/
                {checklist.length || "—"}). At least half the checklist is required to close.
              </p>
            </header>
            {checklist.length > 0 && (
              <ul className="lab-checklist">
                {checklist.map((item) => {
                  const on = checks.includes(item.id);
                  return (
                    <li key={item.id}>
                      <label className={clsx("check-row", on && "on")}>
                        <input
                          type="checkbox"
                          checked={on}
                          onChange={() => {
                            const next = on
                              ? checks.filter((c) => c !== item.id)
                              : [...checks, item.id];
                            void persistChecks(next);
                          }}
                        />
                        <span>{item.label}</span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
            {lesson.lab ? (
              <details className="lab-details" open={checklist.length === 0}>
                <summary>Full LAB.md text</summary>
                <MarkdownView
                  content={lesson.lab}
                  basePath={`lessons/${lesson.id}`}
                />
              </details>
            ) : (
              <p className="empty-hint">LAB missing.</p>
            )}
          </div>
        )}

        {step === "run" && (
          <div className="wizard-pane">
            <header className="wizard-pane-head">
              <h2>Run · {lesson.makeTarget}</h2>
              <p>
                Single-flight: one job at a time. Phase dependencies
                enforced server-side. Log export and retry available.
              </p>
            </header>
            <LiveRunConsole
              defaultAction={lesson.makeTarget}
              compact
              onFinished={(ok) => {
                setRefreshKey((k) => k + 1);
                if (ok) markStep("run");
                void refreshGates();
              }}
            />
          </div>
        )}

        {step === "results" && (
          <div className="wizard-pane">
            <header className="wizard-pane-head">
              <h2>Inspect the results</h2>
              <p>
                Compare artifacts and metrics with{" "}
                <Link href="/materials/reference/golden-metrics.md">
                  golden-metrics
                </Link>
                {lesson.id === "07-finish" && (
                  <>
                    {" "}
                    · SPICE chain:{" "}
                    <Link href="/materials/reference/spice-power-chain.md#lesson-07-finish">
                      finish → PKG
                    </Link>
                    {" "}
                    ·{" "}
                    <Link href="/flow?phase=pkg">FlowLab PKG</Link>
                  </>
                )}
                {lesson.id === "03-floorplan" && (
                  <>
                    {" "}
                    ·{" "}
                    <Link href="/flow?phase=pdn">FlowLab PDN</Link>
                    {" "}
                    ·{" "}
                    <Link href="/materials/reference/spice-power-chain.md#lesson-03-floorplan">
                      grid → mesh
                    </Link>
                  </>
                )}
                .
              </p>
            </header>
            <LessonLayoutPanel
              lessonId={lesson.id}
              makeTarget={lesson.makeTarget}
              refreshKey={refreshKey}
            />
            <ResultsPanel stage={lesson.makeTarget} refreshKey={refreshKey} variant="learn" />
            <div className="lesson-actions" style={{ marginTop: "1rem" }}>
              <a
                className="btn-ghost"
                href={`/tools?stage=${lesson.makeTarget}&tab=results`}
              >
                Open dashboard · {lesson.makeTarget}
              </a>
              <button
                type="button"
                className="btn-primary"
                onClick={async () => {
                  const catalog = await fetch("/api/open").then((r) => r.json());
                  const pick = (
                    catalog.targets as {
                      id: string;
                      stage?: string;
                      kind: string;
                      exists: boolean;
                    }[]
                  ).find(
                    (t) =>
                      t.stage === lesson.makeTarget &&
                      t.kind === "openroad" &&
                      t.exists,
                  );
                  if (!pick) {
                    push("No ODB for this phase", "bad");
                    return;
                  }
                  const res = await fetch("/api/open", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id: pick.id }),
                  });
                  const body = await res.json();
                  if (body.launched) push(body.message, "ok");
                  else if (body.command) {
                    await navigator.clipboard
                      ?.writeText(body.command)
                      .catch(() => undefined);
                    push(body.message || "Command copied", "info");
                  } else push(body.message || "Open failed", "bad");
                }}
              >
                Open OpenROAD GUI
              </button>
            </div>
          </div>
        )}

        {step === "chiudi" && (
          <div className="wizard-pane close-pane">
            <header className="wizard-pane-head">
              <h2>Close the lesson</h2>
              <p>
                The server rejects completion if gates are not green —
                an empty click is not enough.
              </p>
            </header>
            <ul className="gate-list" aria-label="Completion gates">
              {gates.map((g) => (
                <li key={g.id} className={g.ok ? "ok" : "bad"}>
                  <span>{g.ok ? "✓" : "○"}</span>
                  <div>
                    <strong>{g.label}</strong>
                    {g.detail && <em>{g.detail}</em>}
                  </div>
                </li>
              ))}
              {gates.length === 0 && (
                <li className="muted">Loading gates…</li>
              )}
            </ul>
            {completeError && (
              <p className="block-banner" role="alert">
                {completeError}
              </p>
            )}
            <div className="lesson-actions">
              <button
                type="button"
                className="btn-primary"
                onClick={completeLesson}
                disabled={completed || !gatesOk}
                title={
                  gatesOk
                    ? "Mark lesson completed"
                    : "Complete all gates first"
                }
              >
                {completed
                  ? "Already in progress"
                  : gatesOk
                    ? "Mark lesson completed"
                    : "Incomplete gates"}
              </button>
              <button type="button" className="btn-ghost" onClick={() => void refreshGates()}>
                Recalculate gates
              </button>
              {completed && <span className="pill ok">saved</span>}
            </div>
          </div>
        )}

        <footer className="wizard-footer">
          <button
            type="button"
            className="btn-ghost"
            onClick={prevStep}
            disabled={stepIndex === 0}
          >
            Back
          </button>
          <span className="muted">
            Step {stepIndex + 1}/{STEPS.length}
            {saving ? " · saving…" : ""}
          </span>
          {step !== "chiudi" ? (
            <button type="button" className="btn-primary" onClick={nextStep}>
              Next
            </button>
          ) : (
            <Link href="/lessons" className="btn-ghost">
              Back to lessons
            </Link>
          )}
        </footer>
      </div>
    </div>
  );
}

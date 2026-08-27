"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { MarkdownView } from "@/components/MarkdownView";
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
  { id: "teoria", label: "1 · Teoria", short: "Teoria" },
  { id: "lab", label: "2 · LAB", short: "LAB" },
  { id: "run", label: "3 · Esegui", short: "Esegui" },
  { id: "risultati", label: "4 · Risultati", short: "Risultati" },
  { id: "chiudi", label: "5 · Chiudi", short: "Chiudi" },
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
  const [step, setStep] = useState<StepId>("teoria");
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
      push("Lezione segnata come completata", "ok");
      await refreshGates();
      return;
    }
    if (data.gates) {
      setGates(data.gates);
      setGatesOk(false);
    }
    const msg = data.error || "Impossibile completare: gate non soddisfatti";
    setCompleteError(msg);
    push(msg, "bad");
  }

  const stepIndex = STEPS.findIndex((s) => s.id === step);
  const checksDone = checklist.length
    ? checks.filter((c) => checklist.some((i) => i.id === c)).length
    : 0;

  return (
    <div className="wizard">
      <ol className="wizard-steps" aria-label="Passi lezione">
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
        {step === "teoria" && (
          <div className="wizard-pane">
            <header className="wizard-pane-head">
              <h2>Leggi la teoria</h2>
              <p>Quando hai chiaro il contratto di questa fase, passa al LAB.</p>
            </header>
            {lesson.readme ? (
              <MarkdownView
                content={lesson.readme}
                basePath={`lessons/${lesson.id}`}
              />
            ) : (
              <p className="empty-hint">README assente.</p>
            )}
          </div>
        )}

        {step === "lab" && (
          <div className="wizard-pane">
            <header className="wizard-pane-head">
              <h2>Laboratorio interattivo</h2>
              <p>
                Spunta le parti mentre le fai ({checksDone}/
                {checklist.length || "—"}). Serve almeno metà checklist per chiudere.
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
                <summary>Testo completo LAB.md</summary>
                <MarkdownView
                  content={lesson.lab}
                  basePath={`lessons/${lesson.id}`}
                />
              </details>
            ) : (
              <p className="empty-hint">LAB assente.</p>
            )}
          </div>
        )}

        {step === "run" && (
          <div className="wizard-pane">
            <header className="wizard-pane-head">
              <h2>Esegui · {lesson.makeTarget}</h2>
              <p>
                Single-flight: un solo job alla volta. Dipendenze di fase
                bloccate lato server. Export log e retry disponibili.
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

        {step === "risultati" && (
          <div className="wizard-pane">
            <header className="wizard-pane-head">
              <h2>Ispeziona i risultati</h2>
              <p>
                Confronta artefatti e metriche con{" "}
                <Link href="/materiali/reference/golden-metrics.md">
                  golden-metrics
                </Link>
                {lesson.id === "07-finish" && (
                  <>
                    {" "}
                    · catena SPICE:{" "}
                    <Link href="/materiali/reference/spice-power-chain.md#lezione-07-finish">
                      finish → PKG
                    </Link>
                    {" "}
                    ·{" "}
                    <Link href="/flusso?phase=pkg">FlowLab PKG</Link>
                  </>
                )}
                {lesson.id === "03-floorplan" && (
                  <>
                    {" "}
                    ·{" "}
                    <Link href="/flusso?phase=pdn">FlowLab PDN</Link>
                    {" "}
                    ·{" "}
                    <Link href="/materiali/reference/spice-power-chain.md#lezione-03-floorplan">
                      griglia → mesh
                    </Link>
                  </>
                )}
                .
              </p>
            </header>
            <ResultsPanel stage={lesson.makeTarget} refreshKey={refreshKey} />
            <div className="lesson-actions" style={{ marginTop: "1rem" }}>
              <a
                className="btn-ghost"
                href={`/strumenti?stage=${lesson.makeTarget}&tab=results`}
              >
                Apri dashboard · {lesson.makeTarget}
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
                    push("Nessun ODB per questa fase", "bad");
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
                    push(body.message || "Comando copiato", "info");
                  } else push(body.message || "Apertura fallita", "bad");
                }}
              >
                Apri OpenROAD GUI
              </button>
            </div>
          </div>
        )}

        {step === "chiudi" && (
          <div className="wizard-pane close-pane">
            <header className="wizard-pane-head">
              <h2>Chiudi la lezione</h2>
              <p>
                Il server rifiuta il completamento se i gate non sono verdi —
                non basta un click a vuoto.
              </p>
            </header>
            <ul className="gate-list" aria-label="Gate di completamento">
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
                <li className="muted">Caricamento gate…</li>
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
                    ? "Segna lezione completata"
                    : "Completa prima tutti i gate"
                }
              >
                {completed
                  ? "Già nel progresso"
                  : gatesOk
                    ? "Segna lezione completata"
                    : "Gate incompleti"}
              </button>
              <button type="button" className="btn-ghost" onClick={() => void refreshGates()}>
                Ricalcola gate
              </button>
              {completed && <span className="pill ok">salvata</span>}
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
            Indietro
          </button>
          <span className="muted">
            Passo {stepIndex + 1}/{STEPS.length}
            {saving ? " · salvataggio…" : ""}
          </span>
          {step !== "chiudi" ? (
            <button type="button" className="btn-primary" onClick={nextStep}>
              Avanti
            </button>
          ) : (
            <Link href="/lezioni" className="btn-ghost">
              Torna alle lezioni
            </Link>
          )}
        </footer>
      </div>
    </div>
  );
}

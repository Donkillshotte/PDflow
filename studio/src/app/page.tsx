"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SuiteHub } from "@/components/SuiteHub";

type Lesson = {
  id: string;
  num: string;
  title: string;
  completed: boolean;
  makeTarget: string;
};

export default function HomePage() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [ready, setReady] = useState<boolean | null>(null);

  useEffect(() => {
    void Promise.all([
      fetch("/api/lessons").then((r) => r.json()),
      fetch("/api/toolchain").then((r) => r.json()),
    ]).then(([L, T]) => {
      setLessons(L.lessons ?? []);
      setReady(Boolean(T.ready));
    });
  }, []);

  const completed = lessons.filter((l) => l.completed).length;
  const next = lessons.find((l) => !l.completed) ?? lessons[lessons.length - 1];

  return (
    <main>
      <section className="hero">
        <div className="hero-metal" aria-hidden />
        <div className="hero-glow" aria-hidden />
        <div className="hero-copy">
          <p className="hero-brand">OpenROAD</p>
          <h1 className="hero-title">Physical Design, interattivo</h1>
          <p className="hero-lead">
            Percorso guidato per lezione: teoria → LAB con checklist → run con
            log live → ispezione artefatti → chiusura.
          </p>
          <div className="cta-row">
            <Link href="/flusso" className="btn-primary">
              Apri FlowLab interattivo
            </Link>
            {next ? (
              <Link href={`/lezioni/${next.id}`} className="btn-ghost">
                Corso · {next.title}
              </Link>
            ) : (
              <Link href="/lezioni" className="btn-ghost">
                Apri lezioni
              </Link>
            )}
            <Link href="/strumenti" className="btn-ghost">
              Console live
            </Link>
          </div>
          <div className="progress-strip" aria-label={`Progresso ${completed} su 8`}>
            {lessons.map((l) => (
              <Link
                key={l.id}
                href={`/lezioni/${l.id}`}
                className={`progress-dot${l.completed ? " on" : ""}`}
                title={l.title}
              />
            ))}
          </div>
          <p className="footer-note">
            {completed}/8 lezioni · toolchain{" "}
            {ready === null ? "…" : ready ? "pronta" : "da sistemare"}
          </p>
        </div>
      </section>

      <section className="home-rail">
        <div className="home-rail-head">
          <h2 className="section-title">Flusso interattivo</h2>
          <Link href="/flusso" className="home-rail-cta">
            FlowLab · RTL → GDSII →
          </Link>
        </div>
        <div className="flow-steps">
          {[
            { n: "RTL", t: "Verilog", d: "Editor Monaco + sim" },
            { n: "SYN", t: "Sintesi", d: "Yosys · ABC · SDC" },
            { n: "FP", t: "Floorplan", d: "Die · PDN" },
            { n: "PL", t: "Place", d: "GP → DP" },
            { n: "CTS", t: "Clock", d: "Skew · TNS" },
            { n: "RT", t: "Route", d: "Global + detail" },
            { n: "GDS", t: "Finish", d: "Signoff · SPEF" },
          ].map((s) => (
            <Link key={s.n} href={`/flusso?phase=${s.n === "RTL" ? "rtl" : s.n === "SYN" ? "synth" : s.n === "FP" ? "floorplan" : s.n === "PL" ? "place" : s.n === "CTS" ? "cts" : s.n === "RT" ? "route" : "finish"}`} className="flow-step flow-step-link">
              <span>{s.n}</span>
              <strong>{s.t}</strong>
              <em>{s.d}</em>
            </Link>
          ))}
        </div>
      </section>

      <section className="home-rail home-rail-lessons">
        <h2 className="section-title">Corso per lezione</h2>
        <div className="flow-steps">
          {[
            { n: "01", t: "Teoria", d: "README della fase" },
            { n: "02", t: "LAB", d: "Checklist spuntabile" },
            { n: "03", t: "Esegui", d: "Log in streaming" },
            { n: "04", t: "Risultati", d: "Artefatti + golden" },
            { n: "05", t: "Chiudi", d: "Progresso salvato" },
          ].map((s) => (
            <div key={s.n} className="flow-step">
              <span>{s.n}</span>
              <strong>{s.t}</strong>
              <em>{s.d}</em>
            </div>
          ))}
        </div>
      </section>

      <section className="panel home-suite" id="suite">
        <SuiteHub compact />
      </section>
    </main>
  );
}

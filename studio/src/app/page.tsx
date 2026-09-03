"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SuiteHub } from "@/components/SuiteHub";
import { ProductStory } from "@/components/ProductStory";

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
          <h1 className="hero-title">RTL → GDS on OpenROAD</h1>
          <p className="hero-lead">
            Nangate45 / FreePDK45. Signoff is STA → DRC → LVS → power.
            DSE proposes knobs; wins stay in <code>win_rule.py</code>.
            Gold Dynamic IR is 45.298 mV.
          </p>
          <div className="cta-row">
            <Link href="/flow" className="btn-primary">
              Open FlowLab
            </Link>
            {next ? (
              <Link href={`/lessons/${next.id}`} className="btn-ghost">
                Course · {next.title}
              </Link>
            ) : (
              <Link href="/lessons" className="btn-ghost">
                Open lessons
              </Link>
            )}
            <Link href="/tools" className="btn-ghost">
              Tools
            </Link>
          </div>
          <div className="progress-strip" aria-label={`Progress ${completed} of 8`}>
            {lessons.map((l) => (
              <Link
                key={l.id}
                href={`/lessons/${l.id}`}
                className={`progress-dot${l.completed ? " on" : ""}`}
                title={l.title}
              />
            ))}
          </div>
          <p className="footer-note">
            {completed}/8 lessons · toolchain{" "}
            {ready === null ? "…" : ready ? "ready" : "needs setup"}
          </p>
        </div>
      </section>

      <section className="home-rail" id="story">
        <ProductStory />
      </section>

      <section className="home-rail">
        <div className="home-rail-head">
          <h2 className="section-title">Interactive flow</h2>
          <Link href="/flow" className="home-rail-cta">
            FlowLab · RTL → PKG →
          </Link>
        </div>
        <p className="footer-note" style={{ marginTop: "0.5rem" }}>
          Power &amp; SPICE chain:{" "}
          <Link href="/materials/reference/spice-power-chain.md">full guide</Link>
          {" · "}
          <Link href="/pkg">PKG hub</Link>
        </p>
        <div className="flow-steps">
          {[
            { n: "RTL", t: "Verilog", d: "Editor · VCD", ph: "rtl" },
            { n: "SYN", t: "Synthesis", d: "Yosys · .lib", ph: "synth" },
            { n: "FP", t: "Floorplan", d: "Die · PDN", ph: "floorplan" },
            { n: "PDN", t: "Gridcheck", d: "PSM-0040", ph: "pdn" },
            { n: "PL", t: "Place", d: "ITerm sink", ph: "place" },
            { n: "CTS", t: "Clock", d: "Switching", ph: "cts" },
            { n: "RT", t: "Route", d: "SPEF path", ph: "route" },
            { n: "GDS", t: "Finish", d: "IR · power", ph: "finish" },
            { n: "PKG", t: "System", d: "ngspice", ph: "pkg" },
          ].map((s) => (
            <Link key={s.n} href={`/flow?phase=${s.ph}`} className="flow-step flow-step-link">
              <span>{s.n}</span>
              <strong>{s.t}</strong>
              <em>{s.d}</em>
            </Link>
          ))}
        </div>
      </section>

      <section className="home-rail home-rail-lessons">
        <h2 className="section-title">Course per lesson</h2>
        <div className="flow-steps">
          {[
            { n: "01", t: "Theory", d: "Phase README" },
            { n: "02", t: "LAB", d: "Checkable checklist" },
            { n: "03", t: "Run", d: "Streaming log" },
            { n: "04", t: "Results", d: "Artifacts + golden" },
            { n: "05", t: "Close", d: "Progress saved" },
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

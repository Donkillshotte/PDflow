import Link from "next/link";
import { SuiteHub } from "@/components/SuiteHub";
import { ProductStory } from "@/components/ProductStory";
import { getProductStory } from "@/lib/story";
import { HomeHero } from "./home-hero";

export const dynamic = "force-dynamic";

export default function HomePage() {
  const story = getProductStory();

  return (
    <main>
      <HomeHero />

      <section className="home-rail" id="story">
        <ProductStory initial={story} />
      </section>

      <section className="home-rail">
        <div className="home-rail-head">
          <h2 className="section-title">Interactive flow</h2>
          <Link href="/flow" className="home-rail-cta">
            FlowLab · RTL → PKG
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

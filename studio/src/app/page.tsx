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
          <h2 className="section-title">RTL → finish → signoff_all</h2>
          <Link href="/flow" className="home-rail-cta">
            FlowLab
          </Link>
        </div>
        <p className="footer-note" style={{ marginTop: "0.5rem" }}>
          Four pillars: STA → DRC → LVS → power. Leftover must-connect on
          DFF_X2 stays named. ECO close is <code>signoff_all</code> on a copy.
          IR meshes are not interchangeable.
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
            { n: "GDS", t: "Finish", d: "STA · DRC · LVS · power", ph: "finish" },
            { n: "PKG", t: "Package", d: "System PDN", ph: "pkg" },
          ].map((s) => (
            <Link key={s.n} href={`/flow?phase=${s.ph}`} className="flow-step flow-step-link">
              <span>{s.n}</span>
              <strong>{s.t}</strong>
              <em>{s.d}</em>
            </Link>
          ))}
        </div>
      </section>

      <section className="panel home-suite" id="suite">
        <SuiteHub compact />
      </section>
    </main>
  );
}

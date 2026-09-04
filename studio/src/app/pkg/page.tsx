import Link from "next/link";
import { PkgHubPanel } from "@/components/PkgHubPanel";

export const metadata = {
  title: "PKG · System PDN · OpenROAD Studio",
  description: "System PDN ladder and Phase 2 (HotSpot, dummy RDL). Four-pillar signoff stays on finish.",
};

export default function PkgPage() {
  return (
    <main className="pkg-page">
      <header className="page-head">
        <p className="eyebrow">Package</p>
        <h1>PKG · System PDN and Phase 2</h1>
        <p>
          Board / package ladder, HotSpot, and dummy RDL. Chip IR, STA, DRC,
          and LVS close on{" "}
          <Link href="/flow?phase=finish#signoff">finish</Link> via{" "}
          <code>signoff_all</code>.
        </p>
      </header>

      <PkgHubPanel />

      <section className="pkg-hero-stack" aria-label="Stack die to board">
        <div className="pkg-layer board">VRM · regulator + Cout</div>
        <div className="pkg-layer pkg">Board · plane / bulk / HF decap</div>
        <div className="pkg-layer bumps">Package · RLC + bumps</div>
        <div className="pkg-layer chip">Die · C_die + cell currents</div>
      </section>

      <div className="pkg-grid">
        <article className="pkg-card">
          <h2>1. Chip PDN (on finish)</h2>
          <p>
            Gridcheck after floorplan. The on-die mesh and IR ledger live with
            the power pillar on finish, not here.
          </p>
          <Link className="btn-primary" href="/flow?phase=finish#ir">
            Finish IR
          </Link>
        </article>
        <article className="pkg-card">
          <h2>2. System PDN</h2>
          <p>
            ngspice ladder: Z(f) and load-step. Config{" "}
            <code>learn/system_pdn/default.json</code>.
          </p>
          <Link className="btn-primary" href="#system-pdn">
            System PDN
          </Link>
        </article>
        <article className="pkg-card">
          <h2>3. SPICE chain</h2>
          <ul>
            <li>
              <Link href="/materials/reference/spice-power-chain.md">
                Power / SPICE chain · phase links
              </Link>
            </li>
            <li>
              <Link href="/materials/reference/spice-chip-mesh.md">
                Chip mesh · cells and ITerm
              </Link>
            </li>
            <li>
              <Link href="/materials/reference/spice-ngspice-primer.md">
                ngspice · TRAN/AC
              </Link>
            </li>
            <li>
              <Link href="/materials/sim/spice/README.md">Lab netlist</Link>
            </li>
            <li>
              <Link href="/materials/file/sim/spice/nangate_inverter_demo.sp">
                Demo inverter SPICE
              </Link>
            </li>
          </ul>
        </article>
        <article className="pkg-card">
          <h2>4. Commands</h2>
          <ul className="pkg-check">
            <li>
              <code>run_system_pdn.sh</code> — Z(f) and die droop
            </li>
            <li>
              <code>run_thermal_signoff.sh</code> — HotSpot compact model
            </li>
            <li>
              <code>run_pkg_signoff.sh</code> — bump + dummy RDL
            </li>
            <li>
              <code>run_signoff_phase2.sh</code> — Phase 2 orchestrator
            </li>
          </ul>
        </article>
      </div>
    </main>
  );
}

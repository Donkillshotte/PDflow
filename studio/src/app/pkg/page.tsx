import Link from "next/link";
import { PkgHubPanel } from "@/components/PkgHubPanel";
import { ProductStory } from "@/components/ProductStory";

export const metadata = {
  title: "PKG · Design package · OpenROAD Studio",
  description:
    "Hierarchical System PDN, chip mesh SPICE, power chain RTL→PKG.",
};

export default function PkgPage() {
  return (
    <main className="pkg-page">
      <header className="page-head">
        <p className="eyebrow">Design package</p>
        <h1>PKG · Packaging &amp; System PDN</h1>
        <p>
          Full chain: <strong>RTL</strong> (VCD) → <strong>liberty/cells</strong> →{" "}
          <strong>PDN grid</strong> → <strong>finish/report_power</strong> →{" "}
          <strong>mesh SPICE on-die</strong> → <strong>System PDN ngspice</strong>.
        </p>
      </header>

      <ProductStory compact />

      <PkgHubPanel />

      <section className="pkg-hero-stack" aria-label="Stack die to board">
        <div className="pkg-layer board">VRM · regulator + Cout</div>
        <div className="pkg-layer pkg">Board · plane / bulk / HF decap</div>
        <div className="pkg-layer bumps">Package · RLC + bumps</div>
        <div className="pkg-layer chip">Die · C_die + cell currents</div>
      </section>

      <div className="pkg-grid">
        <article className="pkg-card">
          <h2>1. Chip PDN</h2>
          <p>
            Gridcheck after floorplan. SPICE mesh post-finish:{" "}
            <code>write_pg_spice</code> + <code>pdn_transient.py</code>.
          </p>
          <Link className="btn-primary" href="/flow?phase=pdn">
            PDN phase
          </Link>
        </article>
        <article className="pkg-card">
          <h2>2. System PDN</h2>
          <p>
            ngspice ladder: Z(f) and load-step. Config{" "}
            <code>learn/system_pdn/default.json</code>.
          </p>
          <Link className="btn-primary" href="/flow?phase=pkg">
            PKG phase
          </Link>
        </article>
        <article className="pkg-card">
          <h2>3. SPICE chain</h2>
          <ul>
            <li>
              <Link href="/materials/reference/spice-power-chain.md">
                RTL → PKG · phase links
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
              <code>run_power_chain.sh</code> — activity → chip IR → system → export
            </li>
            <li>
              <code>export_spice_lab.sh</code> — netlist in sim/spice/
            </li>
            <li>
              <code>run_chip_pdn_ir.sh</code> — mesh on-die
            </li>
            <li>FlowLab signoff post-finish · SPICE chain</li>
          </ul>
        </article>
      </div>
    </main>
  );
}

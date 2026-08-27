import Link from "next/link";

export const metadata = {
  title: "PKG · Design package · OpenROAD Studio",
  description:
    "System PDN gerarchico, chip mesh SPICE, catena power RTL→PKG.",
};

export default function PkgPage() {
  return (
    <main className="pkg-page">
      <header className="page-head">
        <p className="eyebrow">Design package</p>
        <h1>PKG · Packaging &amp; System PDN</h1>
        <p>
          Catena completa: <strong>RTL</strong> (VCD) → <strong>liberty/celle</strong> →{" "}
          <strong>PDN grid</strong> → <strong>finish/report_power</strong> →{" "}
          <strong>mesh SPICE on-die</strong> → <strong>System PDN ngspice</strong>.
        </p>
      </header>

      <section className="pkg-hero-stack" aria-label="Stack die to board">
        <div className="pkg-layer board">VRM · regolatore + Cout</div>
        <div className="pkg-layer pkg">Board · plane / bulk / HF decap</div>
        <div className="pkg-layer bumps">Package · RLC + bumps</div>
        <div className="pkg-layer chip">Die · C_die + correnti celle</div>
      </section>

      <div className="pkg-grid">
        <article className="pkg-card">
          <h2>1. Chip PDN</h2>
          <p>
            Gridcheck dopo floorplan. Mesh SPICE post-finish:{" "}
            <code>write_pg_spice</code> + <code>pdn_transient.py</code>.
          </p>
          <Link className="btn-primary" href="/flusso?phase=pdn">
            Fase PDN
          </Link>
        </article>
        <article className="pkg-card">
          <h2>2. System PDN</h2>
          <p>
            ngspice ladder: Z(f) e load-step. Config{" "}
            <code>learn/system_pdn/default.json</code>.
          </p>
          <Link className="btn-primary" href="/flusso?phase=pkg">
            Fase PKG
          </Link>
        </article>
        <article className="pkg-card">
          <h2>3. Catena SPICE</h2>
          <ul>
            <li>
              <Link href="/materiali/reference/spice-power-chain.md">
                RTL → PKG · collegamento fasi
              </Link>
            </li>
            <li>
              <Link href="/materiali/reference/spice-chip-mesh.md">
                Mesh chip · celle e ITerm
              </Link>
            </li>
            <li>
              <Link href="/materiali/reference/spice-ngspice-primer.md">
                ngspice · TRAN/AC
              </Link>
            </li>
            <li>
              <Link href="/materiali/sim/spice/README.md">Lab netlist</Link>
            </li>
          </ul>
        </article>
        <article className="pkg-card">
          <h2>4. Comandi</h2>
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
            <li>Signoff FlowLab post-finish · catena SPICE</li>
          </ul>
        </article>
      </div>
    </main>
  );
}

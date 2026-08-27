import Link from "next/link";

export const metadata = {
  title: "PKG · Design package · OpenROAD Studio",
  description:
    "System PDN static+transient, bump/package models e checklist design package.",
};

export default function PkgPage() {
  return (
    <main className="pkg-page">
      <header className="page-head">
        <p className="eyebrow">Design package</p>
        <h1>PKG · Packaging &amp; System PDN</h1>
        <p>
          Analisi power integrity a due livelli: <strong>static IR</strong> con
          OpenROAD PDNSim (bump/strap + package R) e <strong>transient droop</strong>{" "}
          sul mesh <code>write_pg_spice</code> (engine Studio ispirato a VoltSpot /
          vyges-em-ir).
        </p>
      </header>

      <section className="pkg-hero-stack" aria-label="Stack die to board">
        <div className="pkg-layer board">Board / VRM · fuori scope (SI/PI commerciali)</div>
        <div className="pkg-layer pkg">Package R/L · external_resistance + Lpkg</div>
        <div className="pkg-layer bumps">Bumps C4 proxy · source_type BUMPS</div>
        <div className="pkg-layer chip">Chip PDN mesh · PDNSim + transient</div>
      </section>

      <div className="pkg-grid">
        <article className="pkg-card">
          <h2>1. Chip PDN</h2>
          <p>
            Connettività VDD/VSS con <code>check_power_grid</code> dopo floorplan.
          </p>
          <Link className="btn-primary" href="/flusso?phase=pdn">
            Fase PDN
          </Link>
        </article>
        <article className="pkg-card">
          <h2>2. System PDN + transient</h2>
          <p>
            Static STRAPS/FULL/BUMPS + solve transient IR (peak switching, package
            R/L, decap). Report JSON e waveform CSV.
          </p>
          <Link className="btn-primary" href="/flusso?phase=pkg">
            Esegui in FlowLab
          </Link>
        </article>
        <article className="pkg-card">
          <h2>3. Documentazione</h2>
          <ul>
            <li>
              <Link href="/materiali/reference/system-pdn.md">
                System PDN · tool landscape
              </Link>
            </li>
            <li>
              <Link href="/materiali/reference/pkg-design-package.md">
                PKG · design package
              </Link>
            </li>
            <li>
              <Link href="/materiali/reference/extended-flow.md">
                Flusso esteso §8
              </Link>
            </li>
          </ul>
        </article>
        <article className="pkg-card">
          <h2>4. Stack open usato</h2>
          <ul className="pkg-check">
            <li>OpenROAD PDNSim · static IR</li>
            <li>write_pg_spice · mesh R + sink I</li>
            <li>pdn_transient.py · backward-Euler</li>
            <li>ngspice installato (opzionale / futuro)</li>
            <li>Validato: static ≈ OpenROAD (±2%)</li>
          </ul>
        </article>
      </div>
    </main>
  );
}

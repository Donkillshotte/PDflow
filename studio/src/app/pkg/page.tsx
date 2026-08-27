import Link from "next/link";

export const metadata = {
  title: "PKG · Design package · OpenROAD Studio",
  description:
    "Packaging, bump/RDL, system PDN e checklist design package per il corso Physical Design.",
};

export default function PkgPage() {
  return (
    <main className="pkg-page">
      <header className="page-head">
        <p className="eyebrow">Design package</p>
        <h1>PKG · Packaging &amp; System PDN</h1>
        <p>
          Dal chip PDN al package: bump, RDL, modelli IR STRAPS/FULL/BUMPS e
          checklist di consegna. Su GCD nangate45 la parte eseguibile è la demo
          System PDN; la teoria resta onesta sui limiti LEF.
        </p>
      </header>

      <section className="pkg-hero-stack" aria-label="Stack die to board">
        <div className="pkg-layer board">Board / VRM · SI/PI esterni</div>
        <div className="pkg-layer pkg">Package planes · BGA/LGA</div>
        <div className="pkg-layer bumps">Bumps · RDL</div>
        <div className="pkg-layer chip">Chip PDN · ORFS READY</div>
      </section>

      <div className="pkg-grid">
        <article className="pkg-card">
          <h2>1. Chip PDN</h2>
          <p>
            Già nel flusso: <code>pdngen</code> in floorplan + fase{" "}
            <strong>PDN</strong> (<code>check_power_grid</code>).
          </p>
          <Link className="btn-primary" href="/flusso?phase=pdn">
            Apri fase PDN
          </Link>
        </article>
        <article className="pkg-card">
          <h2>2. System PDN</h2>
          <p>
            IR drop con <code>-source_type STRAPS|FULL|BUMPS</code> su{" "}
            <code>6_final.odb</code>.
          </p>
          <Link className="btn-primary" href="/flusso?phase=pkg">
            Esegui in FlowLab
          </Link>
        </article>
        <article className="pkg-card">
          <h2>3. Documentazione</h2>
          <ul>
            <li>
              <Link href="/materiali/reference/pkg-design-package.md">
                PKG · design package
              </Link>
            </li>
            <li>
              <Link href="/materiali/reference/system-pdn.md">System PDN</Link>
            </li>
            <li>
              <Link href="/materiali/reference/extended-flow.md">
                Flusso esteso §8
              </Link>
            </li>
          </ul>
        </article>
        <article className="pkg-card">
          <h2>4. Design package checklist</h2>
          <ul className="pkg-check">
            <li>Netlist + SDC + liberty</li>
            <li>ODB/DEF + PDN strategy</li>
            <li>WNS/TNS · DRC · antenna</li>
            <li>IR drop chip + system PDN log</li>
            <li>GDS + layer manifest</li>
            <li>Bump map / BOM (se tapeout)</li>
          </ul>
          <Link
            className="btn-ghost"
            href="/materiali/workbook/progetto-finale-template.md"
          >
            Template consegna
          </Link>
        </article>
      </div>
    </main>
  );
}

import Link from "next/link";

export const metadata = {
  title: "PKG · Design package · OpenROAD Studio",
  description:
    "System PDN gerarchico (VRM→board→package→die), chip PDN e checklist design package.",
};

export default function PkgPage() {
  return (
    <main className="pkg-page">
      <header className="page-head">
        <p className="eyebrow">Design package</p>
        <h1>PKG · Packaging &amp; System PDN</h1>
        <p>
          Due analisi separate: <strong>System PDN</strong> (VRM → board → package
          → die, Z(f) + load-step con ngspice) e <strong>Chip PDN</strong> (griglia
          on-die, gridcheck / PDNSim opzionale).
        </p>
      </header>

      <section className="pkg-hero-stack" aria-label="Stack die to board">
        <div className="pkg-layer board">VRM · regolatore + Cout</div>
        <div className="pkg-layer pkg">Board · plane / bulk / HF decap</div>
        <div className="pkg-layer bumps">Package · RLC + bumps</div>
        <div className="pkg-layer chip">Die · C_die + corrente di carico</div>
      </section>

      <div className="pkg-grid">
        <article className="pkg-card">
          <h2>1. Chip PDN</h2>
          <p>
            Connettività VDD/VSS con <code>check_power_grid</code> dopo floorplan.
            IR on-die opzionale: <code>run_chip_pdn_ir.sh</code>.
          </p>
          <Link className="btn-primary" href="/flusso?phase=pdn">
            Fase PDN
          </Link>
        </article>
        <article className="pkg-card">
          <h2>2. System PDN</h2>
          <p>
            Ladder gerarchico ngspice: impedance Z(f) al die e transient droop al
            load-step. Config in <code>learn/system_pdn/default.json</code>.
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
            <li>ngspice · System PDN AC + TRAN</li>
            <li>system_pdn_hier.py · report JSON</li>
            <li>OpenROAD gridcheck · Chip PDN</li>
            <li>PDNSim + pdn_transient · chip IR opzionale</li>
          </ul>
        </article>
      </div>
    </main>
  );
}

import Link from "next/link";
import { getProductSnapshot } from "@/lib/product";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Product · OpenROAD Studio",
  description: "Official-netlist cooks and win_rule.py verdicts. Not the lab IR bench.",
};

function signed(v: number | null | undefined, unit: string): string {
  if (v == null || Number.isNaN(v)) return "—";
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(Math.abs(v) < 10 ? 2 : 1)}${unit}`;
}

function num(v: number | null | undefined, digits = 3, unit = ""): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toFixed(digits)}${unit}`;
}

export default function ProductPage() {
  const data = getProductSnapshot();
  const versusBase = data.comparisons.filter((p) => p.versus === "base");

  return (
    <main className="product-page">
      <header className="product-page-head">
        <p className="eyebrow">Product surface</p>
        <h1>{data.title}</h1>
        <p>{data.lead}</p>
        <p className="product-page-rule">{data.rule}</p>
        <p>
          <Link href="/materials/dse/product.md">learn/dse/product.md</Link>
          {" · "}
          <code>learn/dse/win_rule.py</code>
          {" · "}
          Lab IR and DSE extracts stay on <Link href="/lab">/lab</Link>.
        </p>
      </header>

      <section className="product-page-slots" aria-label="Official slots">
        <h2>
          {data.wins} wins · {data.cooks} finished cooks
        </h2>
        <p className="muted">{data.detail}</p>
        <ul>
          {data.slots.map((s) => (
            <li key={s.id}>
              <strong>{s.id}</strong>
              <span>{s.clockNs} ns</span>
              <b>
                {s.wins} win{s.wins === 1 ? "" : "s"}
              </b>
              <em>{s.cooks} cooks</em>
              <em>
                base WNS{" "}
                {s.baseWnsPs != null ? `${s.baseWnsPs} ps` : "—"}
              </em>
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Last cook versus slot base">
        <h2>Last cook vs slot base</h2>
        <p className="muted">
          Area, power, leakage, and IR together. Δ% is improvement vs base
          (positive is better).
        </p>
        <table className="product-win-table">
          <thead>
            <tr>
              <th>Slot</th>
              <th>Verdict</th>
              <th>WNS cook</th>
              <th>ΔWNS</th>
              <th>Δarea</th>
              <th>Δpower</th>
              <th>Δleak</th>
              <th>ΔIR</th>
            </tr>
          </thead>
          <tbody>
            {versusBase.map((p) => (
              <tr key={`${p.design}-base`} className={`is-${p.verdict}`}>
                <td>
                  {p.design}
                  <small>{p.clockNs} ns</small>
                </td>
                <td>{p.verdict}</td>
                <td>{num(p.cook.wnsNs, 4, " ns")}</td>
                <td>{signed(p.delta.wnsPs, " ps")}</td>
                <td>{signed(p.delta.areaPct, "%")}</td>
                <td>{signed(p.delta.powerPct, "%")}</td>
                <td>{signed(p.delta.leakPct, "%")}</td>
                <td>{signed(p.delta.irPct, "%")}</td>
              </tr>
            ))}
            {!versusBase.length && (
              <tr>
                <td colSpan={8}>No finished product cooks in the registry yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}

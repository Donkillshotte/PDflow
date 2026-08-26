import Link from "next/link";
import { MATERIALS, WALKTHROUGHS } from "@/lib/course";

export default function MaterialiPage() {
  const groups = ["Corso", "Riferimento", "GUI", "Workbook", "Tcl"] as const;

  const all = [...MATERIALS, ...WALKTHROUGHS];

  return (
    <main>
      <header className="page-head">
        <h1>Materiali</h1>
        <p>
          Glossario, atlante GUI, metriche d’oro, walkthrough Tcl e workbook —
          leggibili in studio senza aprire il terminale.
        </p>
      </header>

      {groups.map((g) => {
        const items = all.filter((m) => m.group === g);
        if (!items.length) return null;
        return (
          <section key={g} style={{ marginBottom: "1.6rem" }}>
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "1.15rem",
                margin: "0 0 0.6rem",
              }}
            >
              {g}
            </h2>
            <div className="material-list">
              {items.map((m) => (
                <Link key={m.href} href={m.href} className="material-row">
                  <small>{m.group}</small>
                  <strong>{m.title}</strong>
                  <span>{m.description}</span>
                </Link>
              ))}
            </div>
          </section>
        );
      })}
    </main>
  );
}

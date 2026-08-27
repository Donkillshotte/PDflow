"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { MATERIALS, WALKTHROUGHS } from "@/lib/materials-client";

type Shot = { name: string; href: string; label: string };

export default function MaterialiPage() {
  const [q, setQ] = useState("");
  const [shots, setShots] = useState<Shot[]>([]);
  const [lightbox, setLightbox] = useState<Shot | null>(null);

  useEffect(() => {
    void fetch("/api/gallery")
      .then((r) => r.json())
      .then((d) => setShots(d.shots ?? []));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("tab") === "gallery") {
      window.setTimeout(() => {
        document.getElementById("gallery")?.scrollIntoView({ behavior: "smooth" });
      }, 120);
    }
    const qp = params.get("q");
    if (qp) setQ(qp);
  }, []);

  const all = useMemo(() => [...MATERIALS, ...WALKTHROUGHS], []);
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return all;
    return all.filter(
      (m) =>
        m.title.toLowerCase().includes(needle) ||
        m.description.toLowerCase().includes(needle) ||
        m.group.toLowerCase().includes(needle),
    );
  }, [all, q]);

  const groups = ["Corso", "Riferimento", "Packaging", "GUI", "Workbook", "Tcl"] as const;
  const shotFiltered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return shots;
    return shots.filter((s) => s.label.toLowerCase().includes(needle) || s.name.includes(needle));
  }, [shots, q]);

  return (
    <main>
      <header className="page-head">
        <h1>Materiali</h1>
        <p>
          Cerca nel corso, apri i documenti in-app, sfoglia la galleria GUI.
          Palette Ctrl+K per saltare a dashboard e viewer Desktop.
        </p>
      </header>

      <div className="search-bar">
        <input
          type="search"
          placeholder="Cerca: golden, CTS, SPEF, atlas…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Cerca materiali"
        />
        <span className="muted">
          {filtered.length} documenti · {shotFiltered.length} PNG
        </span>
      </div>

      {groups.map((g) => {
        const items = filtered.filter((m) => m.group === g);
        if (!items.length) return null;
        return (
          <section key={g} style={{ marginBottom: "1.6rem" }}>
            <h2 className="section-title">{g}</h2>
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

      <section style={{ marginBottom: "2rem" }} id="gallery">
        <h2 className="section-title">Galleria GUI</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Screenshot reali da <code>learn/reference/gui-shots/</code>. Clic per
          ingrandire.
        </p>
        {shotFiltered.length === 0 ? (
          <p className="empty-hint">Nessuna immagine (o filtro vuoto).</p>
        ) : (
          <div className="gallery-grid">
            {shotFiltered.map((s) => (
              <button
                key={s.name}
                type="button"
                className="gallery-tile"
                onClick={() => setLightbox(s)}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={s.href} alt={s.label} loading="lazy" />
                <span>{s.label}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      {lightbox && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          onClick={() => setLightbox(null)}
        >
          <div className="lightbox-inner" onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={lightbox.href} alt={lightbox.label} />
            <div className="lightbox-bar">
              <strong>{lightbox.label}</strong>
              <button type="button" className="btn-ghost" onClick={() => setLightbox(null)}>
                Chiudi
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

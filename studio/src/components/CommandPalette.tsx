"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { useToast } from "@/components/ToastProvider";

type OpenTarget = {
  id: string;
  label: string;
  kind: string;
  href?: string;
  artifact?: string;
  exists: boolean;
  stage?: string;
  command?: string;
  action?: string;
};

const KIND_LABEL: Record<string, string> = {
  dashboard: "Dashboard",
  gallery: "Galleria",
  doc: "Documento",
  lesson: "Lezione",
  openroad: "OpenROAD GUI",
  klayout: "KLayout",
  run: "Esegui",
  webviewer: "Web Viewer",
};

export function CommandPalette() {
  const router = useRouter();
  const { push } = useToast();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [targets, setTargets] = useState<OpenTarget[]>([]);
  const [display, setDisplay] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    const res = await fetch("/api/open");
    if (!res.ok) return;
    const data = await res.json();
    setTargets(data.targets ?? []);
    setDisplay(data.display ?? null);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setActive(0);
    void load();
    const t = window.setTimeout(() => inputRef.current?.focus(), 30);
    return () => window.clearTimeout(t);
  }, [open, load]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return targets.slice(0, 40);
    const tokens = needle.split(/\s+/).filter(Boolean);
    return targets
      .filter((t) => {
        const hay = [
          t.label,
          t.id,
          t.kind,
          t.stage ?? "",
          t.artifact ?? "",
          t.action ?? "",
          KIND_LABEL[t.kind] ?? "",
        ]
          .join(" ")
          .toLowerCase();
        return tokens.every((tok) => hay.includes(tok));
      })
      .slice(0, 40);
  }, [targets, q]);

  useEffect(() => {
    setActive(0);
  }, [q]);

  async function run(t: OpenTarget) {
    if (
      t.kind === "dashboard" ||
      t.kind === "gallery" ||
      t.kind === "doc" ||
      t.kind === "lesson" ||
      t.kind === "run"
    ) {
      if (t.href) router.push(t.href);
      setOpen(false);
      return;
    }

    if (t.kind === "webviewer") {
      if (!t.exists) {
        push(`Manca ODB per ${t.stage ?? t.label}`, "bad");
        return;
      }
      const res = await fetch("/api/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: t.id }),
      });
      const data = await res.json();
      if (data.ok && data.url) {
        push(data.message || "Web viewer avviato", "ok");
        if (data.navigate) router.push(data.navigate);
        window.setTimeout(() => {
          window.open(data.url, "_blank", "noopener,noreferrer");
        }, 600);
        setOpen(false);
        return;
      }
      push(data.message || "Web viewer non avviato", "bad");
      return;
    }

    if (!t.exists) {
      push(`Manca ${t.artifact ?? t.label}`, "bad");
      return;
    }

    const res = await fetch("/api/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: t.id }),
    });
    const data = await res.json();
    if (data.navigate) {
      router.push(data.navigate);
      setOpen(false);
      return;
    }
    if (data.launched) {
      push(data.message || "GUI avviata — apri Desktop", "ok");
      setOpen(false);
      return;
    }
    if (data.command) {
      await navigator.clipboard?.writeText(data.command).catch(() => undefined);
      push(data.message || "Comando copiato (serve Desktop)", "info");
      setOpen(false);
      return;
    }
    push(data.message || "Impossibile aprire", "bad");
  }

  if (!open) {
    return (
      <button
        type="button"
        className="cmd-trigger"
        onClick={() => setOpen(true)}
        title="Palette comandi (Ctrl+K)"
        aria-label="Apri palette comandi"
      >
        ⌘K
      </button>
    );
  }

  return (
    <div
      className="cmd-backdrop"
      role="presentation"
      onClick={() => setOpen(false)}
    >
      <div
        className="cmd-palette"
        role="dialog"
        aria-modal="true"
        aria-label="Palette comandi"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="cmd-head">
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Apri dashboard, run, lezione, OpenROAD, web viewer…"
            aria-label="Cerca comando"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((i) => Math.min(i + 1, filtered.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter" && filtered[active]) {
                e.preventDefault();
                void run(filtered[active]);
              }
            }}
          />
          <span className="muted">
            {display ? `DISPLAY ${display}` : "no DISPLAY · copia comando"}
          </span>
        </header>
        <ul className="cmd-list" role="listbox">
          {filtered.length === 0 && (
            <li className="muted cmd-empty">Nessun risultato</li>
          )}
          {filtered.map((t, i) => (
            <li key={t.id}>
              <button
                type="button"
                role="option"
                aria-selected={i === active}
                className={clsx(
                  "cmd-item",
                  i === active && "active",
                  !t.exists && "missing",
                )}
                onMouseEnter={() => setActive(i)}
                onClick={() => void run(t)}
              >
                <span className="cmd-kind">{KIND_LABEL[t.kind] ?? t.kind}</span>
                <span className="cmd-label">{t.label}</span>
                {!t.exists && <em className="pill bad">manca</em>}
                {t.exists &&
                  (t.kind === "openroad" ||
                    t.kind === "klayout" ||
                    t.kind === "webviewer") && (
                    <em className="pill ok">apri</em>
                  )}
                {t.kind === "run" && <em className="pill ok">run</em>}
              </button>
            </li>
          ))}
        </ul>
        <footer className="cmd-foot muted">
          ↑↓ naviga · Enter apri · Esc chiudi · Ctrl+K
        </footer>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import type { ProductStory as StoryData } from "@/lib/story";

type Surface = {
  id: string;
  label: string;
  href: string;
  ready: boolean;
  detail: string;
};

type Step = {
  id: string;
  label: string;
  href: string;
  ready: boolean;
  detail: string;
};

type Slot = {
  id: string;
  clockNs: number;
  baseWnsPs: number | null;
  wins: number;
  cooks: number;
};

export type StoryPayload = {
  title: string;
  lead: string;
  variant: string;
  surfaces: Surface[];
  path: Step[];
  pipeline: { ready: number; total: number; finishReady: boolean };
  signoff: { ok: boolean | null; passed: number; total: number; detail: string };
  ir: {
    goldMv: number;
    currentMv: number | null;
    goldPresent: boolean;
    currentPresent: boolean;
    detail: string;
  };
  staIr?: {
    ready: boolean;
    slackNs: number | null;
    slackIrNs: number | null;
    nJoined: number | null;
    nGates: number | null;
    detail: string;
  };
  product: { slots: Slot[]; wins: number; cooks: number; detail: string };
  course: { done: number; total: number; nextId: string | null; nextTitle: string | null };
};

export function ProductStory({
  compact,
  tone = "light",
  initial,
}: {
  compact?: boolean;
  tone?: "light" | "dark";
  initial?: StoryData | StoryPayload | null;
}) {
  const [data, setData] = useState<StoryData | StoryPayload | null>(initial ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initial) return;
    let alive = true;
    void fetch("/api/story")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j) => {
        if (alive) setData(j as StoryPayload);
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, [initial]);

  if (error) {
    return (
      <section className={clsx("product-story", `product-story-${tone}`)}>
        <p className="muted">Story snapshot unavailable: {error}</p>
      </section>
    );
  }
  if (!data) {
    return (
      <section className={clsx("product-story", `product-story-${tone}`, "is-loading")}>
        <p className="muted">Loading story…</p>
      </section>
    );
  }

  return (
    <section
      className={clsx("product-story", `product-story-${tone}`, compact && "product-story-compact")}
      aria-label="RTL to signoff path"
    >
      {!compact && (
        <header className="product-story-head">
          <p className="eyebrow">Three surfaces</p>
          <h2>{data.title}</h2>
          <p className="product-story-lead">{data.lead}</p>
        </header>
      )}

      <ol className="story-path">
        {data.path.map((step, i) => (
          <li key={step.id} className={clsx("story-step", step.ready && "is-ready")}>
            <Link href={step.href}>
              <span className="story-step-n">{i + 1}</span>
              <strong>{step.label}</strong>
              <em>{step.detail}</em>
            </Link>
          </li>
        ))}
      </ol>

      <div className="story-surfaces">
        {data.surfaces.map((s) => (
          <Link key={s.id} href={s.href} className={clsx("story-surface", s.ready && "is-ready")}>
            <span>{s.label}</span>
            <strong>{s.detail}</strong>
          </Link>
        ))}
      </div>

      {!compact && (
        <div className="story-metrics">
          <article>
            <span>FlowLab {data.variant}</span>
            <strong>
              {data.pipeline.ready}/{data.pipeline.total}
            </strong>
            <em>phases with artifacts</em>
          </article>
          <article>
            <span>Signoff</span>
            <strong>
              {data.signoff.passed}/{data.signoff.total}
            </strong>
            <em>{data.signoff.detail}</em>
          </article>
          <article>
            <span>STA IR-aware</span>
            <strong>
              {data.staIr?.ready && data.staIr.slackIrNs != null
                ? `${data.staIr.slackIrNs.toFixed(4)} ns`
                : "—"}
            </strong>
            <em>{data.staIr?.detail ?? "NLDM × ITerm V"}</em>
          </article>
          <article>
            <span>Dynamic IR</span>
            <strong>
              {data.ir.currentPresent && data.ir.currentMv != null
                ? `${Number(data.ir.currentMv).toFixed(3)} mV`
                : `${data.ir.goldMv} mV`}
            </strong>
            <em>{data.ir.detail}</em>
          </article>
          <article>
            <span>Product</span>
            <strong>
              {data.product.wins} wins
            </strong>
            <em>{data.product.slots.map((s) => `${s.id} ${s.wins}`).join(" · ")}</em>
          </article>
        </div>
      )}
    </section>
  );
}

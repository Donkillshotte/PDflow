"use client";

import { useRef, useState } from "react";
import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { FlowLabLayoutCanvas } from "@/components/flowlab/FlowLabLayoutCanvas";
import type { ProductSnapshot } from "@/lib/product";

type ProductTab = "summary" | "checks" | "layout";

function parseProductTab(value: string | null): ProductTab {
  return value === "checks" || value === "layout" ? value : "summary";
}

function signed(value: number | null | undefined, unit: string): string {
  if (value == null || Number.isNaN(value)) return "—";
  return (value > 0 ? "+" : "") + value.toFixed(Math.abs(value) < 10 ? 2 : 1) + unit;
}

function numberValue(value: number | null | undefined, digits = 3, unit = ""): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits) + unit;
}

export function ProductWorkspace({ data }: { data: ProductSnapshot }) {
  const router = useRouter();
  const search = useSearchParams();
  const [tab, setTab] = useState<ProductTab>(() => parseProductTab(search.get("tab")));
  const pendingTab = useRef<ProductTab | null>(null);

  useEffect(() => {
    const next = parseProductTab(search.get("tab"));
    setTab((current) => {
      // Rapid tab clicks can leave an older router.replace in flight. Keep
      // the latest local intent until the URL catches up, rather than letting
      // a stale search param move the panel backwards.
      if (pendingTab.current) {
        if (pendingTab.current === next) pendingTab.current = null;
        else return current;
      }
      return next;
    });
  }, [search]);

  function selectTab(next: ProductTab) {
    pendingTab.current = next;
    setTab(next);
    const query = new URLSearchParams(search.toString());
    query.set("tab", next);
    router.replace(`/product?${query.toString()}`, { scroll: false });
  }

  return (
    <div className="product-workspace">
      <div className="surface-tabs" role="tablist" aria-label="Product views">
        {([
          ["summary", "Summary"],
          ["checks", "Checks"],
          ["layout", "Layout"],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`product-tab-${id}`}
            aria-controls={`product-panel-${id}`}
            aria-selected={tab === id}
            tabIndex={tab === id ? 0 : -1}
            className={"surface-tab" + (tab === id ? " is-active" : "")}
            onClick={() => selectTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "summary" && (
        <section id="product-panel-summary" role="tabpanel" aria-labelledby="product-tab-summary" tabIndex={0} className="product-summary-grid" aria-label="Product summary">
          <article className="product-evidence-card product-evidence-primary">
            <span>Product contract</span>
            <strong>Current invocation only</strong>
            <p>{data.detail}</p>
            <Link href="/flow?phase=finish#signoff" className="btn-primary">Open finish signoff</Link>
          </article>
          <article className="product-evidence-card">
            <span>Evidence</span>
            <strong>{data.cooks} current invocation{data.cooks === 1 ? "" : "s"}</strong>
            <p>Historical metrics are not loaded as a baseline or oracle.</p>
          </article>
          <article className="product-evidence-card">
            <span>Comparison gate</span>
            <strong>{data.comparisons.length ? "Explicit pair available" : "Not comparable"}</strong>
            <p>Both sides must be emitted by the same live invocation and compatible extract.</p>
          </article>
          <div className="product-slot-list">
            {data.slots.map((slot) => (
              <article key={slot.id} className="product-slot">
                <strong>{slot.id}</strong>
                <span>{slot.clockNs != null ? slot.clockNs + " ns" : "current run"}</span>
                <em>{slot.cooks} cook{slot.cooks === 1 ? "" : "s"}</em>
              </article>
            ))}
          </div>
        </section>
      )}

      {tab === "checks" && (
        <section id="product-panel-checks" role="tabpanel" aria-labelledby="product-tab-checks" tabIndex={0} className="product-checks" aria-label="Current invocation checks">
          <div className="product-checks-heading">
            <div>
              <h2>Current-run comparisons</h2>
              <p>Only explicit same-invocation pairs can produce deltas. Missing data remains unavailable.</p>
            </div>
            <span className={"pill " + (data.comparisons.length ? "ok" : "warn")}>
              {data.comparisons.length ? "COMPARABLE" : "NOT_RUN"}
            </span>
          </div>
          <div className="product-table-scroll">
            <table className="product-win-table">
              <thead>
                <tr>
                  <th>Slot</th><th>Verdict</th><th>WNS cook</th><th>ΔWNS</th>
                  <th>Δarea</th><th>Δpower</th><th>Δleak</th><th>ΔIR</th>
                </tr>
              </thead>
              <tbody>
                {data.comparisons.map((pair) => (
                  <tr key={pair.design + "-same-invocation"} className={"is-" + pair.verdict}>
                    <td>{pair.design}<small>{pair.clockNs} ns</small></td>
                    <td>{pair.verdict}</td>
                    <td>{numberValue(pair.cook.wnsNs, 4, " ns")}</td>
                    <td>{signed(pair.delta.wnsPs, " ps")}</td>
                    <td>{signed(pair.delta.areaPct, "%")}</td>
                    <td>{signed(pair.delta.powerPct, "%")}</td>
                    <td>{signed(pair.delta.leakPct, "%")}</td>
                    <td>{signed(pair.delta.irPct, "%")}</td>
                  </tr>
                ))}
                {!data.comparisons.length && (
                  <tr><td colSpan={8}>No same-invocation comparison is available.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "layout" && (
        <section id="product-panel-layout" role="tabpanel" aria-labelledby="product-tab-layout" tabIndex={0} className="product-layout-view" aria-label="Product finish layout">
          <div className="product-layout-heading">
            <div>
              <h2>Finish layout</h2>
              <p>Read-only preview of the current finish artifact. Open native tools from FlowLab for interaction.</p>
            </div>
            <Link href="/flow?phase=finish" className="btn-ghost">Open FlowLab</Link>
          </div>
          <FlowLabLayoutCanvas phaseId="finish" variant="flowlab" refreshKey={0} stageDone />
        </section>
      )}
    </div>
  );
}

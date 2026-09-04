"use client";

import clsx from "clsx";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { POWER_CHAIN, SPICE_ANALYSES, chainForPhase } from "./powerChain";
import { PHASE_IDS } from "./phases";

export function FlowLabPowerChain({
  phaseId,
  compact,
}: {
  phaseId: string;
  compact?: boolean;
}) {
  const current = chainForPhase(phaseId);
  const idx = PHASE_IDS.indexOf(phaseId);

  return (
    <section
      className={clsx("fl-power-chain", compact && "fl-power-chain-compact")}
      aria-label="Power and SPICE chain"
    >
      <div className="fl-power-chain-head">
        <strong>Power / SPICE chain</strong>
        <Link href="/materials/reference/spice-power-chain.md">
          Full SPICE guide
        </Link>
      </div>

      {!compact && (
        <div className="fl-power-chain-track" aria-hidden>
          {POWER_CHAIN.map((node, i) => (
            <span key={node.phaseId} className="fl-power-chain-step-wrap">
              <span
                className={clsx(
                  "fl-power-chain-step",
                  node.phaseId === phaseId && "active",
                  i < idx && "done",
                )}
              >
                {node.label}
              </span>
              {i < POWER_CHAIN.length - 1 && (
                <ChevronRight size={12} className="fl-power-chain-arrow" />
              )}
            </span>
          ))}
        </div>
      )}

      {current && (
        <div className="fl-power-chain-detail">
          <div className="fl-power-chain-col">
            <span className="fl-power-chain-k">Produce</span>
            <ul>
              {current.produces.map((p) => (
                <li key={p}>
                  <code>{p}</code>
                </li>
              ))}
            </ul>
          </div>
          <div className="fl-power-chain-col">
            <span className="fl-power-chain-k">Consume</span>
            <ul>
              {current.consumes.map((c) => (
                <li key={c}>
                  <code>{c}</code>
                </li>
              ))}
            </ul>
          </div>
          <div className="fl-power-chain-col fl-power-chain-spice">
            <span className="fl-power-chain-k">Course lesson</span>
            <p>
              {current.lessonIds.map((id, i) => (
                <span key={id}>
                  {i > 0 && ", "}
                  <Link href={`/lessons/${id}`}>{id}</Link>
                </span>
              ))}
            </p>
          </div>
          {(current.spice || current.doc) && (
            <div className="fl-power-chain-col fl-power-chain-spice">
              <span className="fl-power-chain-k">SPICE / doc</span>
              {current.spice && <p>{current.spice}</p>}
              {current.doc && <Link href={current.doc}>Read more</Link>}
            </div>
          )}
        </div>
      )}

      {(phaseId === "finish" || phaseId === "pdn" || phaseId === "pkg") && (
        <div className="fl-power-chain-extra">
          <span className="fl-power-chain-k">Linked SPICE analyses</span>
          <ul className="fl-power-chain-analyses">
            {SPICE_ANALYSES.map((a) => (
              <li key={a.id}>
                <strong>
                  <Link href={`/tools?tab=run&action=${a.action}`}>{a.label}</Link>
                </strong>
                <span>{a.spice}</span>
                {"doc" in a && a.doc ? (
                  <Link href={a.doc}>doc</Link>
                ) : null}
              </li>
            ))}
          </ul>
          <p className="fl-power-chain-note">
            Lab netlist: <code>learn/sim/spice/</code> · export with{" "}
            <code>export_spice_lab.sh</code> · chain with{" "}
            <code>run_power_chain.sh</code>
          </p>
        </div>
      )}
    </section>
  );
}

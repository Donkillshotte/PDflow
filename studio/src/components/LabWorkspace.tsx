"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { DsePanel } from "@/components/flowlab/DsePanel";
import { LiveRunConsole } from "@/components/LiveRunConsole";
import { LabBench } from "@/components/LabBench";
import { Asap7FlowWorkspace } from "@/components/Asap7FlowWorkspace";

type LabTab = "bench" | "dse" | "provenance";

export function LabWorkspace() {
  const router = useRouter();
  const search = useSearchParams();
  const [tab, setTab] = useState<LabTab>(() => {
    const requested = search.get("tab");
    return requested === "dse" || requested === "provenance" ? requested : "bench";
  });
  const asap7Track = search.get("track") !== "course";
  const asap7Variant = "lab_asap7_gcd_tc_rvt_nldm_7p5";

  useEffect(() => {
    const requested = search.get("tab");
    setTab(requested === "dse" || requested === "provenance" ? requested : "bench");
  }, [search]);

  function selectTab(next: LabTab) {
    setTab(next);
    router.replace(`/lab?tab=${next}`, { scroll: false });
  }

  return (
    <div className="lab-workspace">
      <div className="surface-tabs" role="tablist" aria-label="Lab views">
        {([
          ["bench", "Bench"],
          ["dse", "DSE compare"],
          ["provenance", "Provenance"],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`lab-tab-${id}`}
            aria-controls={`lab-panel-${id}`}
            aria-selected={tab === id}
            tabIndex={tab === id ? 0 : -1}
            className={"surface-tab" + (tab === id ? " is-active" : "")}
            onClick={() => selectTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "bench" && (
        <section id="lab-panel-bench" role="tabpanel" aria-labelledby="lab-tab-bench" tabIndex={0}>
          {asap7Track ? (
            <Asap7FlowWorkspace routeBase="/lab" />
          ) : (
          <>
          <div className="lab-asap7-actions">
            <div>
              <span className="workspace-panel-kicker">ASAP7 native experiments</span>
              <strong>Launch a controlled flow or analysis</strong>
              <p>Runs are serialized by the local resource executor. Outputs stay in the selected ASAP7 lab variant and never become Product signoff.</p>
            </div>
            <div className="lab-asap7-links">
              <Link href={`/flow?platform=asap7&phase=finish&variant=${asap7Variant}`} className="btn-primary btn-sm">Open ASAP7 flow</Link>
              <Link href="/pkg" className="btn-ghost btn-sm">Open System PDN</Link>
            </div>
            <LiveRunConsole
              defaultAction="lab_asap7_flow"
              agentVariant={asap7Variant}
              allowedActions={["lab_asap7_flow", "lab_asap7_pdk", "lab_asap7_pkg", "lab_asap7_chip_pdn"]}
            />
          </div>
          <LabBench tone="dark" />
          </>
          )}
        </section>
      )}
      {tab === "dse" && (
        <section id="lab-panel-dse" role="tabpanel" aria-labelledby="lab-tab-dse" tabIndex={0} className="lab-view-card" aria-label="DSE comparison">
          <div className="lab-view-heading">
            <div>
              <span className="workspace-panel-kicker">Experimental surface</span>
              <h2>DSE proposals and same-run comparisons</h2>
              <p>Results remain proposals. They do not produce a Product signoff badge or replace the current finish oracle.</p>
            </div>
          </div>
          <DsePanel />
        </section>
      )}
      {tab === "provenance" && (
        <section id="lab-panel-provenance" role="tabpanel" aria-labelledby="lab-tab-provenance" tabIndex={0} className="lab-view-card" aria-label="Lab provenance">
          <div className="lab-view-heading">
            <div>
              <span className="workspace-panel-kicker">Experiment contract</span>
              <h2>Mesh, oracle and activity must remain comparable</h2>
              <p>Each experiment identifies its profile, dataset, mesh, oracle and activity scenario. Missing or incompatible inputs are shown as GAP or not comparable.</p>
            </div>
          </div>
          <div className="lab-provenance-grid">
            <article><strong>Scope</strong><span>Lab / ASAP7 / benchmark</span></article>
            <article><strong>Oracle</strong><span>Current invocation only</span></article>
            <article><strong>Promotion</strong><span>Disabled · no Product inference</span></article>
            <article><strong>Documentation</strong><Link href="/materials/reference/dse.md">Open DSE reference</Link></article>
          </div>
        </section>
      )}
    </div>
  );
}

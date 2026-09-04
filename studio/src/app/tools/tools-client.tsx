"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { LiveRunConsole } from "@/components/LiveRunConsole";
import { ResultsPanel } from "@/components/ResultsPanel";
import { OpsDashboard } from "@/components/OpsDashboard";
import { InspectPanel } from "@/components/InspectPanel";
import { FlowLabLayoutCanvas } from "@/components/flowlab/FlowLabLayoutCanvas";
import { LeftoverSuiteStrip } from "@/components/LeftoverSuiteStrip";
import { SuiteHub } from "@/components/SuiteHub";
import { SurfaceRail } from "@/components/SurfaceRail";
import { useToast } from "@/components/ToastProvider";

type Tool = { name: string; ok: boolean; detail: string };
type Status = {
  tools: Tool[];
  orfs: boolean;
  tutorial: boolean;
  ready: boolean;
};

const STAGES = ["synth", "floorplan", "place", "cts", "route", "finish"] as const;
const RUN_ACTIONS = new Set([
  "check",
  "status",
  "list",
  "test_course",
  "rtl_sim",
  "gate_sim",
  "gridcheck",
  "system_pdn",
  "chip_pdn_ir",
  "vyges_em_ir",
  "dynamic_ir",
  "power_chain",
  "activity_power",
  "vectorless",
  "klayout_drc",
  "sta_signoff",
  "sta_ir_aware",
  "drc_signoff",
  "klayout_lvs",
  "yosys_equiv",
  "formal_gcd",
  "openrcx_report",
  "analytical_pex",
  "ccs_char",
  "lvs_deep",
  "layout_tools",
  "spice_engines",
  "tool_matrix",
  ...STAGES,
]);

export default function ToolsClient() {
  const search = useSearchParams();
  const router = useRouter();
  const { push } = useToast();
  const [status, setStatus] = useState<Status | null>(null);
  const [stage, setStage] = useState("synth");
  const [runAction, setRunAction] = useState("check");
  const [tab, setTab] = useState<"ops" | "run" | "results">("ops");
  const [refreshKey, setRefreshKey] = useState(0);
  const [opsKey, setOpsKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [guiBusy, setGuiBusy] = useState(false);
  const resultsRef = useRef<HTMLElement | null>(null);
  const runRef = useRef<HTMLElement | null>(null);
  const opsRef = useRef<HTMLElement | null>(null);
  const suiteRef = useRef<HTMLElement | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      const res = await fetch("/api/toolchain");
      setStatus(await res.json());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    const s = search.get("stage");
    const t = search.get("tab") as "ops" | "run" | "results" | null;
    const a = search.get("action");
    if (s && (STAGES as readonly string[]).includes(s)) setStage(s);
    if (a && RUN_ACTIONS.has(a)) {
      setRunAction(a);
      if ((STAGES as readonly string[]).includes(a)) setStage(a);
      if (!t) setTab("run");
    } else if (s && (STAGES as readonly string[]).includes(s)) {
      setRunAction(s);
    }
    if (t === "ops" || t === "run" || t === "results") setTab(t);
  }, [search]);

  useEffect(() => {
    if (typeof window !== "undefined" && window.location.hash === "#suite") {
      window.setTimeout(() => {
        suiteRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
      return;
    }
    const map = { ops: opsRef, run: runRef, results: resultsRef } as const;
    const el = map[tab]?.current;
    if (el) {
      window.setTimeout(() => {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    }
  }, [tab, stage, runAction]);

  function goStage(next: string, nextTab: "ops" | "run" | "results" = "results") {
    setStage(next);
    setRunAction(next);
    setTab(nextTab);
    router.replace(
      `/tools?stage=${next}&tab=${nextTab}&action=${next}`,
      { scroll: false },
    );
  }

  async function openDefaultGui() {
    setGuiBusy(true);
    try {
      const catalog = await fetch("/api/open").then((r) => r.json());
      const list = catalog.targets as {
        id: string;
        stage?: string;
        kind: string;
        exists: boolean;
      }[];
      const pick =
        list.find((t) => t.stage === stage && t.kind === "openroad" && t.exists) ??
        list.find((t) => t.stage === stage && t.exists);
      if (!pick) {
        push(`No GUI ready for ${stage}`, "bad");
        return;
      }
      const res = await fetch("/api/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: pick.id }),
      });
      const body = await res.json();
      if (body.launched) push(body.message, "ok");
      else if (body.command) {
        await navigator.clipboard?.writeText(body.command).catch(() => undefined);
        push(body.message || "Command copied", "info");
      } else push(body.message || "Open failed", "bad");
    } finally {
      setGuiBusy(false);
    }
  }

  return (
    <main className="studio-pro-page">
      <SurfaceRail />
      <header className="studio-pro-banner">
        <div>
          <p className="studio-pro-eyebrow">OpenROAD Studio · Tools</p>
          <h1>Toolchain and run console</h1>
          <p>
            Course variant <code>learn</code>. FlowLab variant{" "}
            <code>flowlab</code>. Do not mix them. Leftover named stays on
            the suite, not hidden behind a green check.
          </p>
          <LeftoverSuiteStrip compact />
        </div>
        <Link href="/flow" className="btn-primary">
          Open FlowLab →
        </Link>
      </header>

      <header className="page-head page-head-compact">
        <p>
          Deep-link, Ctrl+K palette, run/inspect/viewer, and Open GUI
          (OpenROAD / KLayout) on the learn variant.
        </p>
      </header>

      <div className="lesson-actions">
        <button type="button" className="btn-ghost" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh toolchain"}
        </button>
        {status?.ready ? (
          <span className="pill ok">environment ready</span>
        ) : status ? (
          <span className="pill bad">something missing</span>
        ) : (
          <span className="pill">…</span>
        )}
        <button
          type="button"
          className="btn-primary"
          onClick={() => void openDefaultGui()}
          disabled={guiBusy}
        >
          {guiBusy ? "Opening…" : `Open GUI · ${stage}`}
        </button>
      </div>

      <div className="stage-jump" role="navigation" aria-label="Go to phase">
        {STAGES.map((s) => (
          <button
            key={s}
            type="button"
            className={`chip ${stage === s ? "chip-active" : ""}`}
            onClick={() => goStage(s, "results")}
          >
            <span>{s}</span>
            <em>dashboard</em>
          </button>
        ))}
      </div>

      <div className="tool-grid">
        {(status?.tools ?? []).map((t) => (
          <div key={t.name} className="tool-card">
            <strong>
              {t.name}{" "}
              <span className={`pill ${t.ok ? "ok" : "bad"}`}>
                {t.ok ? "ok" : "no"}
              </span>
            </strong>
            <span>{t.detail}</span>
          </div>
        ))}
        <div className="tool-card">
          <strong>
            ORFS{" "}
            <span className={`pill ${status?.orfs ? "ok" : "bad"}`}>
              {status?.orfs ? "ok" : "no"}
            </span>
          </strong>
          <span>tools/OpenROAD-flow-scripts/flow</span>
        </div>
        <div className="tool-card">
          <strong>
            Tutorial GCD{" "}
            <span className={`pill ${status?.tutorial ? "ok" : "bad"}`}>
              {status?.tutorial ? "ok" : "no"}
            </span>
          </strong>
          <span>learn/designs/nangate45/gcd-tutorial</span>
        </div>
      </div>

      <section
        className="panel panel-pro"
        style={{ marginBottom: "1.2rem" }}
        ref={suiteRef}
        id="suite"
      >
        <SuiteHub />
      </section>

      <section className="panel panel-pro" style={{ marginBottom: "1.2rem" }} ref={opsRef} id="ops">
        <OpsDashboard
          refreshKey={opsKey}
          onOpenStage={(s) => goStage(s, "results")}
        />
      </section>

      <section className="panel panel-pro" style={{ marginBottom: "1.2rem" }} ref={runRef} id="run">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          Run · {runAction}
        </h2>
        <LiveRunConsole
          defaultAction={runAction}
          key={runAction}
          onFinished={(_ok, action) => {
            if ((STAGES as readonly string[]).includes(action)) {
              goStage(action, "results");
              setRefreshKey((k) => k + 1);
            }
            setOpsKey((k) => k + 1);
          }}
        />
      </section>

      <section className="panel panel-pro" ref={resultsRef} id="results">
        {(STAGES as readonly string[]).includes(stage) && stage !== "rtl" && (
          <div className="lesson-layout-panel" style={{ marginBottom: "1rem" }}>
            <FlowLabLayoutCanvas
              phaseId={
                stage as "synth" | "floorplan" | "place" | "cts" | "route" | "finish"
              }
              variant="learn"
              refreshKey={refreshKey}
              stageDone
            />
          </div>
        )}
        <ResultsPanel stage={stage} refreshKey={refreshKey} />
      </section>

      <section className="panel panel-pro" style={{ marginTop: "1.2rem" }} id="inspect">
        <InspectPanel stage={stage} refreshKey={refreshKey} />
      </section>
    </main>
  );
}

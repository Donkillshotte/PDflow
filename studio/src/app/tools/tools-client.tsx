"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import clsx from "clsx";
import { LiveRunConsole } from "@/components/LiveRunConsole";
import { ResultsPanel } from "@/components/ResultsPanel";
import { OpsDashboard } from "@/components/OpsDashboard";
import { InspectPanel } from "@/components/InspectPanel";
import { FlowLabLayoutCanvas } from "@/components/flowlab/FlowLabLayoutCanvas";
import { LeftoverSuiteStrip } from "@/components/LeftoverSuiteStrip";
import { SuiteHub } from "@/components/SuiteHub";
import { useToast } from "@/components/ToastProvider";

type Tool = { name: string; ok: boolean; detail: string; required?: boolean };
type Status = {
  tools: Tool[];
  orfs: boolean;
  tutorial: boolean;
  ready: boolean;
};

type RegistryTool = {
  tool_id: string;
  display_name: string;
  required?: boolean;
  capabilities?: string[];
  required_dependencies?: string[];
  availability?: string;
  executable?: string | null;
  version?: string | null;
};

const STAGES = ["synth", "floorplan", "place", "cts", "route", "finish"] as const;
type ToolsTab = "suite" | "ops" | "run" | "results";

function parseToolsTab(value: string | null): ToolsTab | null {
  // `registry` was the public label used by the command palette and older
  // deep links. Keep it as an additive alias for the internal `suite` tab so
  // opening a registry link never silently falls back to Operations.
  if (value === "registry") return "suite";
  return value === "suite" || value === "ops" || value === "run" || value === "results"
    ? value
    : null;
}

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
  "power_signoff",
  "power_chain",
  "activity_power",
  "vectorless",
  "export_spice_lab",
  "klayout_drc",
  "sta_signoff",
  "sta_ir_aware",
  "drc_signoff",
  "klayout_lvs",
  "signoff_all",
  "eco",
  "eco_apply",
  "eco_close",
  "thermal_signoff",
  "pkg_rdl",
  "pkg_signoff",
  "signoff_phase2",
  "yosys_equiv",
  "formal_gcd",
  "openrcx_report",
  "analytical_pex",
  "ccs_char",
  "lab_asap7_pdk",
  "lab_asap7_pkg",
  "lab_asap7_chip_pdn",
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
  const [stage, setStage] = useState(() => {
    const requested = search.get("stage");
    if (requested && (STAGES as readonly string[]).includes(requested)) return requested;
    const action = search.get("action");
    return action && (STAGES as readonly string[]).includes(action) ? action : "synth";
  });
  const [runAction, setRunAction] = useState(() => {
    const requested = search.get("action");
    return requested && RUN_ACTIONS.has(requested) ? requested : "check";
  });
  const [tab, setTab] = useState<ToolsTab>(() => {
    const fromQuery = parseToolsTab(search.get("tab"));
    if (fromQuery) return fromQuery;
    return typeof window !== "undefined" && window.location.hash === "#suite"
      ? "suite"
      : "ops";
  });
  const [registry, setRegistry] = useState<RegistryTool[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [opsKey, setOpsKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [guiBusy, setGuiBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [toolchainResponse, registryResponse] = await Promise.all([
        fetch("/api/toolchain", { cache: "no-store" }),
        fetch("/api/registry", { cache: "no-store" }),
      ]);
      if (!toolchainResponse.ok) throw new Error(`HTTP ${toolchainResponse.status}`);
      setStatus(await toolchainResponse.json());
      if (registryResponse.ok) {
        const data = (await registryResponse.json()) as { tools?: RegistryTool[] };
        setRegistry(Array.isArray(data.tools) ? data.tools : []);
      } else {
        setRegistry([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Toolchain status unavailable");
    } finally {
      setLoading(false);
    }
  }

  const requiredMissing = (status?.tools ?? []).filter(
    (tool) => tool.required !== false && !tool.ok,
  ).length;

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    const s = search.get("stage");
    const t = parseToolsTab(search.get("tab"));
    const a = search.get("action");
    if (s && (STAGES as readonly string[]).includes(s)) setStage(s);
    if (a && RUN_ACTIONS.has(a)) {
      setRunAction(a);
      if ((STAGES as readonly string[]).includes(a)) setStage(a);
      if (!t) setTab("run");
    } else if (s && (STAGES as readonly string[]).includes(s)) {
      setRunAction(s);
    }
    if (t) setTab(t);
    if (window.location.hash === "#suite" && !t) setTab("suite");
  }, [search]);

  function goStage(next: string, nextTab: "ops" | "run" | "results" = "results") {
    setStage(next);
    setRunAction(next);
    setTab(nextTab);
    router.replace(
      `/tools?stage=${next}&tab=${nextTab}&action=${next}`,
      { scroll: false },
    );
  }

  function selectTab(next: ToolsTab) {
    setTab(next);
    router.replace(
      "/tools?stage=" +
        encodeURIComponent(stage) +
        "&tab=" +
        next +
        "&action=" +
        encodeURIComponent(runAction),
      { scroll: false },
    );
  }

  async function openDefaultGui() {
    setGuiBusy(true);
    try {
      const catalogResponse = await fetch("/api/open");
      if (!catalogResponse.ok) throw new Error(`Open catalog HTTP ${catalogResponse.status}`);
      const catalog = (await catalogResponse.json()) as { targets?: unknown };
      const list = (Array.isArray(catalog.targets) ? catalog.targets : []) as {
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
    } catch (e) {
      push(e instanceof Error ? e.message : "Open GUI failed", "bad");
    } finally {
      setGuiBusy(false);
    }
  }

  return (
    <main className="studio-pro-page">
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
          <span className="pill ok">native environment ready</span>
        ) : status ? (
          <span className="pill bad">
            {requiredMissing ? `${requiredMissing} required tool${requiredMissing === 1 ? "" : "s"} missing` : "environment needs attention"}
          </span>
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

      {error && (
        <p className="block-banner" role="alert">
          Toolchain status unavailable: {error}
        </p>
      )}

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

      <div className="tools-tabs" role="tablist" aria-label="Tools workspace views">
        {([
          ["suite", "Registry"],
          ["ops", "Operations"],
          ["run", "Run"],
          ["results", "Results"],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`tools-tab-${id}`}
            aria-controls={`tools-panel-${id}`}
            aria-selected={tab === id}
            tabIndex={tab === id ? 0 : -1}
            className={clsx("tools-tab", tab === id && "is-active")}
            onClick={() => selectTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "suite" && (
        <section className="panel panel-pro tools-view" id="tools-panel-suite" role="tabpanel" aria-labelledby="tools-tab-suite" tabIndex={0}>
          <div className="tool-registry">
            <div className="tool-registry-head">
              <div>
                <p className="studio-pro-eyebrow">Native registry</p>
                <h2>Installed tools and capabilities</h2>
                <p className="muted">
                  Availability is probed by the local agent. Missing optional tools
                  remain GAP and never become a signoff result.
                </p>
              </div>
              <span className="pill">{loading ? "Loading…" : `${registry.length} registered`}</span>
            </div>
            <div className="tool-registry-scroll">
              <table className="tool-registry-table">
                <caption>PDflow native tool registry</caption>
                <thead>
                  <tr>
                    <th scope="col">Tool</th>
                    <th scope="col">Status</th>
                    <th scope="col">Version</th>
                    <th scope="col">Capabilities</th>
                    <th scope="col">Dependencies</th>
                    <th scope="col">Executable</th>
                  </tr>
                </thead>
                <tbody>
                  {registry.map((tool) => {
                    const availability = tool.availability || "MISSING";
                    const statusClass = availability === "READY"
                      ? "ok"
                      : availability === "UNVERIFIED" || tool.required === false
                        ? "warn"
                        : "bad";
                    return (
                      <tr key={tool.tool_id}>
                        <th scope="row">
                          <strong>{tool.display_name}</strong>
                          <small>{tool.tool_id}</small>
                        </th>
                        <td><span className={clsx("pill", statusClass)}>{availability}</span></td>
                        <td className="mono-hint">{tool.version || "—"}</td>
                        <td>{(tool.capabilities || []).join(" · ") || "—"}</td>
                        <td>{(tool.required_dependencies || []).join(" · ") || "none declared"}</td>
                        <td><code>{tool.executable || "not found"}</code></td>
                      </tr>
                    );
                  })}
                  {loading && (
                    <tr><td colSpan={6} className="muted">Probing native tools…</td></tr>
                  )}
                  {!loading && !registry.length && (
                    <tr><td colSpan={6} className="muted">Registry unavailable — refresh after the local agent starts.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          <div className="tools-suite-divider" aria-hidden="true" />
          <SuiteHub />
        </section>
      )}

      {tab === "ops" && (
        <section className="panel panel-pro tools-view" id="tools-panel-ops" role="tabpanel" aria-labelledby="tools-tab-ops" tabIndex={0}>
          <OpsDashboard
            refreshKey={opsKey}
            onOpenStage={(s) => goStage(s, "results")}
          />
        </section>
      )}

      {tab === "run" && (
        <section className="panel panel-pro tools-view" id="tools-panel-run" role="tabpanel" aria-labelledby="tools-tab-run" tabIndex={0}>
          <h2 className="tools-view-title">Run · {runAction}</h2>
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
      )}

      {tab === "results" && (
        <section className="panel panel-pro tools-view" id="tools-panel-results" role="tabpanel" aria-labelledby="tools-tab-results" tabIndex={0}>
          {(STAGES as readonly string[]).includes(stage) && stage !== "rtl" && (
            <div className="lesson-layout-panel tools-layout-preview">
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
          <div className="tools-inspection">
            <InspectPanel stage={stage} refreshKey={refreshKey} />
          </div>
        </section>
      )}
    </main>
  );
}

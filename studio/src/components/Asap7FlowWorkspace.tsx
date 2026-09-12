"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import clsx from "clsx";
import { ExternalLink, FlaskConical, Gauge, RefreshCw, ShieldCheck, TerminalSquare } from "lucide-react";
import { LiveRunConsole } from "@/components/LiveRunConsole";
import { AnalysisRail } from "@/components/AnalysisRail";
import { AnalysisBundleLauncher } from "@/components/AnalysisBundleLauncher";
import { FlowLabLayoutCanvas } from "@/components/flowlab/FlowLabLayoutCanvas";

const DEFAULT_VARIANT = "lab_asap7_gcd_tc_rvt_nldm_7p5";
const SAFE_VARIANT = /^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$/;

type Asap7Phase = "synth" | "floorplan" | "pdn" | "place" | "cts" | "route" | "finish";
type CheckpointStage = "synth" | "floorplan" | "place" | "cts" | "route" | "finish";

const PHASES: Array<{ id: Asap7Phase; label: string; artifact: string }> = [
  { id: "synth", label: "Synth", artifact: "1_synth.odb" },
  { id: "floorplan", label: "Floorplan", artifact: "2_4_floorplan_pdn.odb" },
  { id: "pdn", label: "Chip PDN", artifact: "2_4_floorplan_pdn.odb" },
  { id: "place", label: "Place", artifact: "3_5_place_dp.odb" },
  { id: "cts", label: "CTS", artifact: "4_cts.odb" },
  { id: "route", label: "Route", artifact: "5_2_route.odb" },
  { id: "finish", label: "Finish", artifact: "6_final.odb" },
];

type Profile = {
  design: string;
  corner: "BC" | "TC" | "WC";
  vt: string;
  libModel: "NLDM" | "CCS";
  track: "7p5" | "6";
  clkPs: string;
  clusterFlops: boolean;
};

type StageRecord = { done?: boolean; artifact?: string };
type Qor = {
  wnsPs?: number | null;
  tnsPs?: number | null;
  areaUm2?: number | null;
  powerMw?: number | null;
  irDropVddMv?: number | null;
  fmaxGhz?: number | null;
  timingClosed?: boolean;
};

type LabEvidence = {
  status?: "pass" | "fail" | "blocked" | "not_run";
  honesty?: "GAP" | "PROXY" | "PARTIAL";
  honestyReason?: string | null;
  leftovers?: { id: string; message: string; count?: number | null }[];
  toolId?: string | null;
  licenseClass?: string | null;
};

type Asap7Snapshot = {
  variant?: string | null;
  design?: string | null;
  corner?: string | null;
  vt?: string[];
  libModel?: string | null;
  track?: string | null;
  clkPs?: number | null;
  status?: LabEvidence["status"];
  honesty?: LabEvidence["honesty"];
  honestyReason?: string | null;
  leftovers?: LabEvidence["leftovers"];
  meshId?: string | null;
  meshFingerprint?: string | null;
  toolId?: string | null;
  licenseClass?: string | null;
  labAdmit?: boolean;
  labAdmitReason?: string | null;
  thermal?: LabEvidence;
  pillars?: { ir?: LabEvidence; thermal?: LabEvidence };
  stages?: Record<string, StageRecord> | null;
  qor?: Qor | null;
  pkg?: { ok?: boolean; nBumps?: number | null; droopMv?: number | null } | null;
  chipPdn?: { ok?: boolean; meshTransientMv?: number | null } | null;
};

type LabResponse = { asap7?: Asap7Snapshot | null };

const DEFAULT_PROFILE: Profile = {
  design: "gcd",
  corner: "TC",
  vt: "RVT",
  libModel: "NLDM",
  track: "7p5",
  clkPs: "310",
  clusterFlops: false,
};

function finite(value: unknown): number | null {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value: unknown, digits = 2): string {
  const number = finite(value);
  return number == null ? "—" : number.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function EvidenceAxis({ label, evidence }: { label: string; evidence?: LabEvidence }) {
  const honesty = evidence?.honesty ?? "GAP";
  const status = evidence?.status ?? "not_run";
  return (
    <div className={clsx("asap7-evidence-axis", `is-${honesty.toLowerCase()}`)}>
      <span>{label}</span>
      <strong>{honesty}</strong>
      <em>status · {status}</em>
      {evidence?.honestyReason ? <small>{evidence.honestyReason}</small> : null}
    </div>
  );
}

function EvidenceLeftovers({ leftovers }: { leftovers?: LabEvidence["leftovers"] }) {
  if (!leftovers?.length) return <p className="asap7-leftovers-empty">No named leftovers emitted.</p>;
  return (
    <ul className="asap7-leftovers" aria-label="ASAP7 named leftovers">
      {leftovers.map((leftover, index) => (
        <li key={`${leftover.id}-${index}`}>
          <code>{leftover.id}</code>
          <span>{leftover.message}</span>
          {leftover.count != null ? <em>×{leftover.count}</em> : null}
        </li>
      ))}
    </ul>
  );
}

function profileVariant(profile: Profile): string {
  const design = profile.design.replaceAll("-", "_");
  const vt = profile.vt.trim().toLowerCase().replace(/[+,\s]+/g, "+");
  const bits = [
    "lab_asap7",
    design,
    profile.corner.toLowerCase(),
    vt || "rvt",
    profile.libModel.toLowerCase(),
    profile.track,
  ];
  const defaultClock = profile.design === "uart" ? "270" : profile.design === "gcd" || profile.design === "gcd-ccs" ? "310" : "";
  if (profile.clkPs && profile.clkPs !== defaultClock) bits.push(`${profile.clkPs}ps`);
  if (profile.clusterFlops) bits.push("mbff");
  return bits.join("_");
}

function phaseFromQuery(value: string | null): Asap7Phase {
  return PHASES.some((phase) => phase.id === value) ? (value as Asap7Phase) : "finish";
}

function checkpointStage(value: string): CheckpointStage | null {
  return ["synth", "floorplan", "place", "cts", "route", "finish"].includes(value)
    ? (value as CheckpointStage)
    : null;
}

function profileFromSnapshot(snapshot: Asap7Snapshot): Profile {
  const design = snapshot.design && ["gcd", "gcd-ccs", "uart", "minimal", "riscv32i-mock-sram"].includes(snapshot.design)
    ? snapshot.design
    : DEFAULT_PROFILE.design;
  const corner = snapshot.corner === "BC" || snapshot.corner === "WC" ? snapshot.corner : "TC";
  const libModel = snapshot.libModel === "CCS" ? "CCS" : "NLDM";
  const track = snapshot.track === "6" ? "6" : "7p5";
  return {
    design,
    corner,
    vt: Array.isArray(snapshot.vt) && snapshot.vt.length ? snapshot.vt.join("+") : "RVT",
    libModel,
    track,
    clkPs: snapshot.clkPs == null ? "" : String(snapshot.clkPs),
    clusterFlops: false,
  };
}

function profileFromVariant(value: string | null): Profile | null {
  if (!value || !SAFE_VARIANT.test(value)) return null;
  const body = value.slice("lab_asap7_".length);
  const designToken = [
    "riscv32i_mock_sram",
    "gcd_ccs",
    "minimal",
    "gcd",
    "uart",
  ].find((token) => body === token || body.startsWith(`${token}_`));
  if (!designToken) return null;
  const fields = body.slice(designToken.length).replace(/^_/, "").split("_");
  const [corner, vt, libModel, track, ...extras] = fields;
  if (
    !(corner === "bc" || corner === "tc" || corner === "wc") ||
    !vt ||
    !(libModel === "nldm" || libModel === "ccs") ||
    !(track === "7p5" || track === "6")
  ) {
    return null;
  }
  const design = designToken === "gcd_ccs" ? "gcd-ccs" : designToken.replaceAll("_", "-");
  const clock = extras.find((item) => /^\d+ps$/.test(item));
  return {
    design,
    corner: corner.toUpperCase() as Profile["corner"],
    vt: vt.toUpperCase(),
    libModel: libModel.toUpperCase() as Profile["libModel"],
    track: track as Profile["track"],
    clkPs: clock ? clock.slice(0, -2) : "",
    clusterFlops: extras.includes("mbff"),
  };
}

export function Asap7FlowWorkspace({ routeBase = "/flow" }: { routeBase?: "/flow" | "/lab" }) {
  const router = useRouter();
  const search = useSearchParams();
  const requestedVariant = search.get("variant");
  const safeRequestedVariant = requestedVariant && SAFE_VARIANT.test(requestedVariant) ? requestedVariant : null;
  const requestedVariantRef = useRef(safeRequestedVariant);
  const [phase, setPhase] = useState<Asap7Phase>(() => phaseFromQuery(search.get("phase")));
  const [profile, setProfile] = useState<Profile>(() => profileFromVariant(safeRequestedVariant) ?? DEFAULT_PROFILE);
  const profileRef = useRef(profile);
  const [variant, setVariant] = useState(() => safeRequestedVariant ?? DEFAULT_VARIANT);
  const [snapshot, setSnapshot] = useState<Asap7Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [requestedRun, setRequestedRun] = useState<{
    action: string;
    token: number;
    parameters?: Record<string, unknown>;
  } | null>(null);
  const requestToken = useRef(0);
  const profileChanged = useRef(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const response = await fetch("/api/lab", { cache: "no-store" });
      if (!response.ok) throw new Error(`Lab snapshot HTTP ${response.status}`);
      const body = (await response.json()) as LabResponse;
      const next = body.asap7 ?? null;
      setSnapshot(next);
      if (next && !profileChanged.current) {
        const requested = requestedVariantRef.current;
        if (!requested || requested === next.variant) {
          const nextProfile = profileFromSnapshot(next);
          profileRef.current = nextProfile;
          setProfile(nextProfile);
          if (next.variant && SAFE_VARIANT.test(next.variant)) setVariant(next.variant);
        }
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Lab snapshot unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    setPhase(phaseFromQuery(search.get("phase")));
  }, [search]);

  useEffect(() => {
    const onEvent = (event: Event) => {
      const detail = (event as CustomEvent<{ type?: string }>).detail;
      if (["tool.completed", "tool.failed", "artifact.changed", "report.updated"].includes(detail?.type ?? "")) {
        setRefreshKey((value) => value + 1);
        void refresh();
      }
    };
    window.addEventListener("pdflow:agent-event", onEvent);
    return () => window.removeEventListener("pdflow:agent-event", onEvent);
  }, [refresh]);

  const runParameters = useMemo(() => {
    const value: Record<string, unknown> = {
      design: profile.design,
      corner: profile.corner,
      vt: profile.vt,
      lib_model: profile.libModel,
      track: profile.track,
      cluster_flops: profile.clusterFlops,
    };
    const clkPs = finite(profile.clkPs);
    if (clkPs != null) value.clk_ps = clkPs;
    return value;
  }, [profile]);

  const currentSnapshot = snapshot?.variant === variant ? snapshot : null;
  const selectedPhase = PHASES.find((item) => item.id === phase) ?? PHASES[PHASES.length - 1]!;
  const stageKey: CheckpointStage = phase === "pdn" ? "floorplan" : phase;
  const stageDone = currentSnapshot?.stages?.[stageKey]?.done === true;
  const irEvidence = currentSnapshot?.pillars?.ir ?? (currentSnapshot ? {
    status: currentSnapshot.status,
    honesty: currentSnapshot.honesty,
    honestyReason: currentSnapshot.honestyReason,
    leftovers: currentSnapshot.leftovers,
    toolId: currentSnapshot.toolId,
    licenseClass: currentSnapshot.licenseClass,
  } : undefined);
  const thermalEvidence = currentSnapshot?.pillars?.thermal ?? currentSnapshot?.thermal;

  function updateProfile<K extends keyof Profile>(key: K, value: Profile[K]) {
    profileChanged.current = true;
    // Keep rapid select/input changes coherent while Next processes the
    // client-side URL transition. React state may still contain the previous
    // render when two controls are changed in the same interaction burst.
    const next = { ...profileRef.current, [key]: value } as Profile;
    profileRef.current = next;
    setProfile(next);
    const nextVariant = profileVariant(next);
    if (SAFE_VARIANT.test(nextVariant)) {
      setVariant(nextVariant);
      router.replace(
        `${routeBase}?platform=asap7&phase=${encodeURIComponent(phase)}&variant=${encodeURIComponent(nextVariant)}`,
        { scroll: false },
      );
    }
  }

  function selectPhase(next: Asap7Phase) {
    setPhase(next);
    router.replace(`${routeBase}?platform=asap7&phase=${encodeURIComponent(next)}&variant=${encodeURIComponent(variant)}`, { scroll: false });
  }

  function requestAnalysisRun(
    action: string,
    checkpoint = stageKey,
    parameters?: Record<string, unknown>,
  ) {
    // ASAP7 chip-PDN is the native adapter currently available for on-die IR.
    // The policy rail still keeps signal EM and unsupported checkpoint actions
    // read-only rather than pretending that another operation is equivalent.
    const nativeAction = action === "chip_pdn_ir" || action === "dynamic_ir" ? "lab_asap7_chip_pdn" : action;
    requestToken.current += 1;
    setRequestedRun({
      action: nativeAction,
      token: requestToken.current,
      parameters: ["gridcheck", "sta_checkpoint"].includes(nativeAction)
        ? { ...(parameters ?? {}), checkpoint }
        : parameters,
    });
  }

  return (
    <div className="asap7-workbench">
      <header className="asap7-workbench-header">
        <div className="asap7-workbench-title">
          <div className="asap7-brand-mark" aria-hidden="true">A7</div>
          <div>
            <span className="workspace-panel-kicker">Standalone lab · native execution</span>
            <h1>ASAP7 physical design workbench</h1>
            <p>RTL → GDS checkpoints, native OpenROAD sessions and repeatable experiments. This surface is Lab evidence, never Product signoff.</p>
          </div>
        </div>
        <div className="asap7-workbench-links">
          <span className="asap7-scope-badge"><FlaskConical size={14} aria-hidden /> LAB · ASAP7</span>
          <Link href="/lab" className="btn-ghost btn-sm">Lab bench</Link>
          <Link href={`/pkg?platform=asap7&variant=${encodeURIComponent(variant)}`} className="btn-ghost btn-sm">Package / PDN</Link>
          <Link href="/tools?tab=registry" className="btn-ghost btn-sm"><ExternalLink size={13} aria-hidden /> Tools</Link>
        </div>
      </header>

      {loadError && (
        <p className="block-banner" role="alert">
          ASAP7 snapshot unavailable: {loadError}
        </p>
      )}

      <nav className="asap7-phase-tabs" aria-label="ASAP7 flow checkpoints">
        {PHASES.map((item) => {
          const done = currentSnapshot?.stages?.[item.id === "pdn" ? "floorplan" : item.id]?.done === true;
          return (
            <button
              key={item.id}
              type="button"
              className={clsx("asap7-phase-tab", phase === item.id && "is-active", done && "is-done")}
              aria-current={phase === item.id ? "step" : undefined}
              onClick={() => selectPhase(item.id)}
            >
              <span>{item.label}</span>
              <small>{done ? "ready" : item.artifact}</small>
            </button>
          );
        })}
      </nav>

      <div className="asap7-workbench-grid">
        <section className="asap7-viewer-column" aria-label="ASAP7 design viewer">
          <div className="asap7-viewer-heading">
            <div>
              <span className="workspace-panel-kicker">Design canvas</span>
              <strong>{selectedPhase.label} · {variant}</strong>
            </div>
            <div className="asap7-viewer-status">
              <span className={clsx("pill", stageDone ? "ok" : "warn")}>{stageDone ? "ARTIFACT READY" : "NOT RUN"}</span>
              <span>{loading ? "Refreshing…" : currentSnapshot ? "live snapshot" : "profile not cooked"}</span>
              <button type="button" className="icon-button" onClick={() => { setRefreshKey((value) => value + 1); void refresh(); }} aria-label="Refresh ASAP7 snapshot" title="Refresh ASAP7 snapshot">
                <RefreshCw size={14} aria-hidden />
              </button>
            </div>
          </div>
          <div className="asap7-canvas-frame">
            <FlowLabLayoutCanvas
              phaseId={phase}
              variant={variant}
              refreshKey={refreshKey}
              stageDone={stageDone}
              allowCandidate={false}
            />
          </div>
        </section>

        <aside className="asap7-control-column" aria-label="ASAP7 experiment controls">
          <section className="asap7-control-section">
            <div className="asap7-section-heading">
              <div>
                <span className="workspace-panel-kicker">Experiment profile</span>
                <h2>Configure a native cook</h2>
              </div>
              <span className="pill neutral">isolated output</span>
            </div>
            <div className="asap7-form-grid">
              <label>
                Design
                <select value={profile.design} onChange={(event) => updateProfile("design", event.target.value)}>
                  <option value="gcd">GCD</option>
                  <option value="gcd-ccs">GCD · CCS</option>
                  <option value="uart">UART</option>
                  <option value="minimal">Minimal</option>
                  <option value="riscv32i-mock-sram">RISC-V mock SRAM</option>
                </select>
              </label>
              <label>
                Corner
                <select value={profile.corner} onChange={(event) => updateProfile("corner", event.target.value as Profile["corner"])}>
                  <option value="BC">BC · FF · 0.77 V</option>
                  <option value="TC">TC · TT · 0.70 V</option>
                  <option value="WC">WC · SS · 0.63 V</option>
                </select>
              </label>
              <label>
                VT set
                <select value={profile.vt} onChange={(event) => updateProfile("vt", event.target.value)}>
                  <option value="RVT">RVT</option>
                  <option value="LVT">LVT</option>
                  <option value="SLVT">SLVT</option>
                  <option value="RVT+LVT">RVT + LVT</option>
                </select>
              </label>
              <label>
                Library
                <select value={profile.libModel} onChange={(event) => updateProfile("libModel", event.target.value as Profile["libModel"])}>
                  <option value="NLDM">NLDM</option>
                  <option value="CCS">CCS · if fetched</option>
                </select>
              </label>
              <label>
                Track
                <select value={profile.track} onChange={(event) => updateProfile("track", event.target.value as Profile["track"])}>
                  <option value="7p5">7.5-track · enabled</option>
                  <option value="6">6-track · fetch-gated</option>
                </select>
              </label>
              <label>
                Clock period · ps
                <input value={profile.clkPs} inputMode="numeric" pattern="[0-9]*" onChange={(event) => updateProfile("clkPs", event.target.value.replace(/[^0-9]/g, ""))} placeholder="design default" />
              </label>
            </div>
            <label className="asap7-checkbox">
              <input type="checkbox" checked={profile.clusterFlops} onChange={(event) => updateProfile("clusterFlops", event.target.checked)} />
              Enable MBFF clustering
            </label>
            <p className="asap7-profile-note"><code>{variant}</code> · profile changes select a new isolated result directory; existing finish files are never overwritten.</p>
          </section>

          <section className="asap7-control-section asap7-qor-section">
            <div className="asap7-section-heading">
              <div>
                <span className="workspace-panel-kicker">Current evidence</span>
                <h2>{currentSnapshot ? "Measured ASAP7 snapshot" : "No snapshot for profile"}</h2>
              </div>
              <Gauge size={16} aria-hidden />
            </div>
            <div className="asap7-qor-grid">
              <div><span>WNS</span><strong className={currentSnapshot?.qor?.wnsPs != null && currentSnapshot.qor.wnsPs < 0 ? "warn" : ""}>{formatNumber(currentSnapshot?.qor?.wnsPs)} ps</strong></div>
              <div><span>Area</span><strong>{formatNumber(currentSnapshot?.qor?.areaUm2)} µm²</strong></div>
              <div><span>Power</span><strong>{formatNumber(currentSnapshot?.qor?.powerMw)} mW</strong></div>
              <div><span>IR drop</span><strong>{formatNumber(currentSnapshot?.qor?.irDropVddMv)} mV</strong></div>
              <div><span>Fmax</span><strong>{formatNumber(currentSnapshot?.qor?.fmaxGhz, 3)} GHz</strong></div>
              <div><span>Timing</span><strong>{currentSnapshot?.qor?.timingClosed == null ? "—" : currentSnapshot.qor.timingClosed ? "closed" : "open"}</strong></div>
            </div>
            <p className="asap7-evidence-note"><ShieldCheck size={13} aria-hidden /> Values are read from the selected live report. Missing, open or proxy results stay visible as such.</p>
          </section>

          <section id="bspdn" className="asap7-control-section asap7-evidence-contract" aria-label="ASAP7 BSPDN evidence">
            <div className="asap7-section-heading">
              <div>
                <span className="workspace-panel-kicker">Lab evidence contract</span>
                <h2>IR / thermal honesty</h2>
              </div>
              <span className={clsx("pill", currentSnapshot?.labAdmit ? "ok" : "warn")}>
                {currentSnapshot?.labAdmit ? "PROXY-FIRST OK" : "NOT ADMITTED"}
              </span>
            </div>
            <div className="asap7-evidence-axes">
              <EvidenceAxis label="IR claim class" evidence={irEvidence} />
              <EvidenceAxis label="Thermal claim class" evidence={thermalEvidence} />
            </div>
            <p className="asap7-evidence-contract-note">
              Honesty is primary; status is the tool outcome. Thermal GAP/not-run remains explicit and cannot be the sole PROXY-first blocker.
            </p>
            <div className="asap7-evidence-identity">
              <span>mesh <code>{currentSnapshot?.meshId ?? "—"}</code></span>
              <span>tool <code>{currentSnapshot?.toolId ?? "—"}</code></span>
              <span>license <code>{currentSnapshot?.licenseClass ?? "—"}</code></span>
            </div>
            <div className="asap7-evidence-leftover-box">
              <strong>Named leftovers</strong>
              <EvidenceLeftovers leftovers={currentSnapshot?.leftovers ?? irEvidence?.leftovers} />
            </div>
            <p className="asap7-evidence-admit-reason">{currentSnapshot?.labAdmitReason ?? "proxy BSPDN row not available"}</p>
          </section>

          <AnalysisBundleLauncher
            stage={phase}
            variant={variant}
            onQueued={() => setRefreshKey((value) => value + 1)}
          />
          <AnalysisRail
            stage={phase}
            variant={variant}
            refreshKey={refreshKey}
            onRunAction={(action, check, parameters) =>
              requestAnalysisRun(action, checkpointStage(check.stage) ?? stageKey, parameters)
            }
          />

          <section className="asap7-control-section asap7-action-section">
            <div className="asap7-section-heading">
              <div>
                <span className="workspace-panel-kicker">Native job runner</span>
                <h2>Launch from this workspace</h2>
              </div>
              <TerminalSquare size={16} aria-hidden />
            </div>
            <LiveRunConsole
              defaultAction="lab_asap7_flow"
              agentVariant={variant}
              allowedActions={[
                "lab_asap7_flow",
                "lab_asap7_pdk",
                "lab_asap7_pkg",
                "lab_asap7_chip_pdn",
                "gridcheck",
                "sta_checkpoint",
              ]}
              runParameters={runParameters}
              requestedRun={requestedRun}
              onFinished={() => {
                setRefreshKey((value) => value + 1);
                window.setTimeout(() => void refresh(), 500);
              }}
            />
          </section>
        </aside>
      </div>
    </div>
  );
}

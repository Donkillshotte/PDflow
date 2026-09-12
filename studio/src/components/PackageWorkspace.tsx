"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  PkgHubPanel,
  type PkgPreview,
  type SystemPreview,
  type ThermalPreview,
} from "@/components/PkgHubPanel";
import { Asap7PackagePanel } from "@/components/Asap7PackagePanel";
import { FlowLabLayoutCanvas } from "@/components/flowlab/FlowLabLayoutCanvas";
import { PackageManifestPanel } from "@/components/PackageManifestPanel";
import type { PackageManifest } from "@/lib/pdflowContracts";

const DEFAULT_ASAP7_VARIANT = "lab_asap7_gcd_tc_rvt_nldm_7p5";

type PackageTab = "system" | "layout" | "geometry" | "connectivity" | "docs";

function parsePackageTab(value: string | null): PackageTab {
  return value === "layout" || value === "geometry" || value === "connectivity" || value === "docs"
    ? value
    : "system";
}

function layoutNumber(value: unknown, digits = 2): string {
  const number = typeof value === "number" && Number.isFinite(value) ? value : null;
  return number == null
    ? "—"
    : number.toLocaleString("en-US", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
}

function PackageLayoutView({
  manifest,
  variant,
  asap7,
}: {
  manifest: PackageManifest | null;
  variant: string;
  asap7: boolean;
}) {
  const die = manifest?.interface?.die || {};
  const bump = manifest?.bump_array || {};
  const rdl = manifest?.rdl || {};
  const dieWidth = typeof die.width_um === "number" ? die.width_um : null;
  const dieHeight = typeof die.height_um === "number" ? die.height_um : null;
  const configuredBumps = bump.configured_count ?? null;
  const observedBumps = bump.observed_component_count ?? null;
  const requiredNets = rdl.required_nets?.length || 0;
  const routedNets = rdl.routed_nets?.length || 0;
  const finishReady = manifest?.checkpoint?.ready === true;
  const platform = asap7 ? "asap7" : "course";

  return (
    <section
      id="package-panel-layout"
      role="tabpanel"
      aria-labelledby="package-tab-layout"
      tabIndex={0}
      className="pkg-layout-view pkg-workspace-panel"
      aria-label="Package finish layout"
    >
      <div className="pkg-layout-heading">
        <div>
          <span className="workspace-panel-kicker">FlowLab continuity · physical layout</span>
          <h2>Finish die and package breakout</h2>
          <p>
            ODB-backed finish layout with the package boundary kept in view. The
            package sidecar and RDL remain Lab evidence; Product signoff stays on
            the finish surface.
          </p>
        </div>
        <div className="pkg-layout-heading-actions">
          <span className={"pill " + (finishReady ? "ok" : "warn")}>
            {finishReady ? "FINISH READY" : "WAITING FOR FINISH"}
          </span>
          <Link
            href={`/flow?platform=${platform}&phase=finish&variant=${encodeURIComponent(variant)}`}
            className="btn-ghost btn-sm"
          >
            Open FlowLab
          </Link>
        </div>
      </div>

      <div className="pkg-layout-facts" aria-label="Package layout facts">
        <article className="pkg-layout-fact accent">
          <span>Die envelope</span>
          <strong>
            {dieWidth != null && dieHeight != null
              ? `${layoutNumber(dieWidth)} × ${layoutNumber(dieHeight)} µm`
              : "—"}
          </strong>
          <small>current finish boundary</small>
        </article>
        <article className="pkg-layout-fact">
          <span>Bump array</span>
          <strong>
            {bump.columns ?? "—"} × {bump.rows ?? "—"}
          </strong>
          <small>
            {configuredBumps ?? "—"} configured · {observedBumps ?? "—"} observed
          </small>
        </article>
        <article className="pkg-layout-fact">
          <span>RDL breakout</span>
          <strong>
            {routedNets}/{requiredNets || "—"} nets
          </strong>
          <small>{rdl.layers?.join(" / ") || "layers unavailable"}</small>
        </article>
        <article className="pkg-layout-fact warn">
          <span>Boundary</span>
          <strong>Lab-scoped</strong>
          <small>product_signoff = false</small>
        </article>
      </div>

      <FlowLabLayoutCanvas
        phaseId="pkg"
        variant={variant}
        refreshKey={0}
        stageDone={finishReady}
        allowCandidate={!asap7}
      />

      <div className="pkg-layout-footer">
        <span>
          Package geometry and node assignments are available in <strong>Geometry</strong>;
          route coverage is available in <strong>Connectivity</strong>.
        </span>
        <span className="pkg-layout-footer-code">variant · {variant}</span>
      </div>
    </section>
  );
}

export function PackageWorkspace({
  system,
  thermal,
  pkg,
  asap7 = false,
  initialVariant,
}: {
  system: SystemPreview | null;
  thermal: ThermalPreview | null;
  pkg: PkgPreview | null;
  asap7?: boolean;
  initialVariant?: string;
}) {
  const router = useRouter();
  const search = useSearchParams();
  const [tab, setTab] = useState<PackageTab>(() => parsePackageTab(search.get("tab")));
  const [manifest, setManifest] = useState<PackageManifest | null>(null);
  const [effectiveVariant, setEffectiveVariant] = useState<string | undefined>(
    initialVariant,
  );

  useEffect(() => {
    setTab(parsePackageTab(search.get("tab")));
  }, [search]);

  useEffect(() => {
    let active = true;
    setEffectiveVariant(initialVariant);
    async function loadManifest() {
      try {
        let variant = initialVariant;
        if (!variant && asap7) {
          const labResponse = await fetch("/api/lab", { cache: "no-store" });
          if (labResponse.ok) {
            const lab = (await labResponse.json()) as {
              asap7?: { variant?: string | null } | null;
            };
            variant = lab.asap7?.variant || undefined;
          }
        }
        const query = variant
          ? "?variant=" + encodeURIComponent(variant)
          : "";
        const response = await fetch("/api/package" + query, {
          cache: "no-store",
        });
        const payload = response.ok
          ? ((await response.json()) as { manifest?: PackageManifest | null })
          : null;
        if (active) {
          setEffectiveVariant(variant);
          setManifest(payload?.manifest || null);
        }
      } catch {
        if (active) setManifest(null);
      }
    }
    void loadManifest();
    return () => {
      active = false;
    };
  }, [asap7, initialVariant]);

  const pathLedgerHref = effectiveVariant
    ? "/api/path-ledger?variant=" + encodeURIComponent(effectiveVariant)
    : "/api/path-ledger";

  function selectTab(next: PackageTab) {
    setTab(next);
    const query = new URLSearchParams(search.toString());
    query.set("tab", next);
    router.replace(`/pkg?${query.toString()}`, { scroll: false });
  }

  return (
    <div className="fl-pro pkg-pro package-workbench">
      <div className="package-workspace">
      <div className="pkg-workspace-tabs" role="tablist" aria-label="Package views">
        {([
          ["system", "System PDN"],
          ["layout", "Layout"],
          ["geometry", "Geometry"],
          ["connectivity", "Connectivity"],
          ["docs", "References"],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`package-tab-${id}`}
            aria-controls={`package-panel-${id}`}
            aria-selected={tab === id}
            tabIndex={tab === id ? 0 : -1}
            className={"pkg-workspace-tab" + (tab === id ? " is-active" : "")}
            onClick={() => selectTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "system" && (
        <section id="package-panel-system" role="tabpanel" aria-labelledby="package-tab-system" tabIndex={0} className="pkg-workspace-panel">
          {asap7 ? (
            <Asap7PackagePanel initialVariant={initialVariant} />
          ) : (
            <PkgHubPanel initialSystem={system} initialThermal={thermal} initialPkg={pkg} />
          )}
        </section>
      )}

      {tab === "layout" && (
        <PackageLayoutView
          manifest={manifest}
          variant={
            effectiveVariant ?? (asap7 ? DEFAULT_ASAP7_VARIANT : "flowlab")
          }
          asap7={asap7}
        />
      )}

      {tab === "geometry" && (
        <section id="package-panel-geometry" role="tabpanel" aria-labelledby="package-tab-geometry" tabIndex={0} className="pkg-workspace-panel" aria-label="Package geometry">
          <PackageManifestPanel manifest={manifest} view="geometry" />
        </section>
      )}

      {tab === "connectivity" && (
        <section id="package-panel-connectivity" role="tabpanel" aria-labelledby="package-tab-connectivity" tabIndex={0} className="pkg-workspace-panel" aria-label="Package connectivity">
          <div className="pkg-connectivity-actions">
            <Link href={pathLedgerHref} className="fl-btn fl-btn-ghost">Open path ledger API</Link>
          </div>
          <PackageManifestPanel manifest={manifest} view="connectivity" />
        </section>
      )}

      {tab === "docs" && (
        <section id="package-panel-docs" role="tabpanel" aria-labelledby="package-tab-docs" tabIndex={0} className="pkg-workspace-panel package-view-card" aria-label="Package references">
          <div className="package-view-heading">
            <div>
              <span className="workspace-panel-kicker">Reference material</span>
              <h2>System PDN and SPICE chain</h2>
              <p>Documentation and commands remain available without taking space from the live analysis view.</p>
            </div>
          </div>
          <ul className="package-reference-list">
            <li><Link href="/materials/reference/spice-power-chain.md">Power / SPICE chain</Link></li>
            <li><Link href="/materials/reference/spice-chip-mesh.md">Chip mesh · cells and ITerm</Link></li>
            <li><Link href="/materials/reference/spice-ngspice-primer.md">ngspice · TRAN/AC</Link></li>
            <li><Link href="/materials/sim/spice/README.md">Lab netlist</Link></li>
            <li><Link href="/materials/file/sim/spice/nangate_inverter_demo.sp">Demo inverter SPICE</Link></li>
          </ul>
        </section>
      )}
      </div>
    </div>
  );
}

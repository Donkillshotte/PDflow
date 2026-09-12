"use client";

import { useMemo, useState } from "react";
import type {
  PackageManifest,
  PackageManifestCheck,
  ReportStatus,
} from "@/lib/pdflowContracts";

type ManifestView = "overview" | "geometry" | "connectivity";

function statusClass(status?: string) {
  return status === "PASS" || status === "PROXY"
    ? "ok"
    : status === "FAIL"
      ? "bad"
      : "warn";
}

function statusText(status?: string) {
  return status || "NOT_RUN";
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatNumber(value: unknown, digits = 2): string {
  const numeric = numberValue(value);
  return numeric == null
    ? "—"
    : numeric.toLocaleString("en-US", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
}

function checkStatus(
  checks: PackageManifestCheck[] | undefined,
  id: string,
  fallback: ReportStatus = "NOT_RUN",
): ReportStatus {
  const row = checks?.find((check) => check.id === id);
  return row?.status || (row?.ok ? "PASS" : fallback);
}

function netClass(row: Record<string, unknown> | undefined): string {
  const value = String(row?.class || "reserved").toLowerCase();
  return value === "power" || value === "ground" || value === "signal"
    ? value
    : "reserved";
}

function shortHash(hash?: string | null): string {
  return hash ? hash.slice(0, 10) + "…" + hash.slice(-6) : "not hashed";
}

function Metric({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: "accent" | "ok" | "warn";
}) {
  return (
    <article className={"pkg-manifest-metric" + (tone ? " " + tone : "")}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </article>
  );
}

function StatusRail({ manifest }: { manifest: PackageManifest }) {
  const checks = manifest.checks;
  const bumpUniqueStatus = checkStatus(checks, "bump_map_unique", "GAP");
  const bumpObservedStatus = checkStatus(
    checks,
    "bump_map_observed",
    bumpUniqueStatus,
  );
  const bumpStatus =
    bumpUniqueStatus === "FAIL" ? "FAIL" : bumpObservedStatus;
  const finishCheckpointStatus = checkStatus(
    checks,
    "finish_checkpoint",
    "GAP",
  );
  const finishInterfaceStatus = checkStatus(
    checks,
    "finish_interface_nets",
    finishCheckpointStatus,
  );
  const items = [
    [
      "finish_interface_nets",
      "Interface",
      finishCheckpointStatus === "GAP" ? "GAP" : finishInterfaceStatus,
    ],
    ["bump_map_observed", "Bump map", bumpStatus],
    ["rdl_net_coverage", "RDL", checkStatus(checks, "rdl_net_coverage", "GAP")],
    ["system_pdn_live", "System PDN", checkStatus(checks, "system_pdn_live", "GAP")],
    ["product_boundary", "Product boundary", "PROXY" as ReportStatus],
  ] as const;

  return (
    <ol className="pkg-manifest-rail" aria-label="Package evidence status">
      {items.map(([id, label, status], index) => (
        <li key={id} className={"pkg-manifest-rail-item " + statusClass(status)}>
          <span className="pkg-manifest-rail-dot">{index + 1}</span>
          <span>
            <strong>{label}</strong>
            <small>{statusText(status)}</small>
          </span>
        </li>
      ))}
    </ol>
  );
}

function BumpMap({ manifest }: { manifest: PackageManifest }) {
  const [selected, setSelected] = useState<string | null>(null);
  const bump = manifest.bump_array || {};
  const rows = Math.max(1, Number(bump.rows) || 1);
  const columns = Math.max(1, Number(bump.columns) || 1);
  const cell = 42;
  const inset = 28;
  const width = inset * 2 + columns * cell;
  const height = inset * 2 + rows * cell;
  const entries = useMemo(
    () => (Array.isArray(bump.map) ? bump.map : []),
    [bump.map],
  );
  const byCoordinate = useMemo(
    () =>
      new Map(
        entries.map((row) => [
          String(Number(row.row)) + "_" + String(Number(row.column)),
          row,
        ]),
      ),
    [entries],
  );
  const selectedRow =
    (selected && entries.find((row) => row.instance === selected)) ||
    entries.find((row) => row.net);

  return (
    <div className="pkg-manifest-map-wrap">
      <div className="pkg-manifest-map-head">
        <div>
          <span className="pkg-section-kicker">Physical interface</span>
          <h3>Bump array · {bump.master || "master unavailable"}</h3>
        </div>
        <span className="pkg-manifest-map-size">
          {columns} × {rows} · pitch{" "}
          {Array.isArray(bump.pitch_um)
            ? bump.pitch_um.map((value) => formatNumber(value, 2)).join(" / ")
            : "—"}{" "}
          µm
        </span>
      </div>
      <div className="pkg-manifest-map-layout">
        <svg
          className="pkg-manifest-bump-map"
          viewBox={"0 0 " + width + " " + height}
          role="img"
          aria-label={
            "Configured " + columns + " by " + rows + " package bump map"
          }
        >
          <rect
            x={inset - 10}
            y={inset - 10}
            width={columns * cell + 20}
            height={rows * cell + 20}
            rx="12"
            className="pkg-map-die"
          />
          {Array.from({ length: rows }, (_, rowIndex) =>
            Array.from({ length: columns }, (_, columnIndex) => {
              const key = String(rowIndex) + "_" + String(columnIndex);
              const entry = byCoordinate.get(key);
              const x = inset + columnIndex * cell + cell / 2;
              const y = inset + (rows - rowIndex - 1) * cell + cell / 2;
              const role = netClass(entry);
              const instance =
                String(entry?.instance || "BUMP_" + rowIndex + "_" + columnIndex);
              const active = selected === instance;
              return (
                <g
                  key={key}
                  className={
                    "pkg-map-node " + role + (active ? " selected" : "")
                  }
                  role="button"
                  tabIndex={0}
                  aria-label={
                    instance + " " + String(entry?.net || "reserved")
                  }
                  onClick={() => setSelected(instance)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelected(instance);
                    }
                  }}
                >
                  <circle cx={x} cy={y} r="13" />
                  <text x={x} y={y + 3} textAnchor="middle">
                    {entry?.net ? String(entry.net).slice(0, 4) : "·"}
                  </text>
                </g>
              );
            }),
          )}
        </svg>
        <div className="pkg-manifest-map-side">
          <div className="pkg-map-legend">
            {(["power", "ground", "signal", "reserved"] as const).map((role) => (
              <span key={role}>
                <i className={"pkg-map-swatch " + role} />
                {role}
              </span>
            ))}
          </div>
          <div className="pkg-map-inspector">
            <span className="pkg-section-kicker">Selected node</span>
            <strong>{String(selectedRow?.instance || "none")}</strong>
            <span>{String(selectedRow?.net || "reserved")}</span>
            <small>
              {selectedRow
                ? String(selectedRow.class || "signal") +
                  " · " +
                  String(selectedRow.role || "mapped")
                : "Click a node to inspect the configured map"}
            </small>
          </div>
          <div className="pkg-map-footnote">
            Origin{" "}
            {Array.isArray(bump.origin_um)
              ? bump.origin_um.map((value) => formatNumber(value, 2)).join(" / ")
              : "—"}{" "}
            µm · configured {bump.configured_count ?? "—"} · observed{" "}
            {bump.observed_component_count ?? "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

function RdlConnectivity({ manifest }: { manifest: PackageManifest }) {
  const rdl = manifest.rdl || {};
  const required = rdl.required_nets || [];
  const routed = new Set(rdl.routed_nets || []);
  const rows = Array.isArray(rdl.nets) ? rdl.nets : [];
  const rowByNet = new Map(
    rows.map((row) => [String(row.net || ""), row]),
  );
  const nets = required.length
    ? required
    : rows.map((row) => String(row.net || "")).filter(Boolean);

  return (
    <section className="pkg-manifest-section">
      <div className="pkg-manifest-section-head">
        <div>
          <span className="pkg-section-kicker">Connectivity evidence</span>
          <h3>RDL route coverage</h3>
        </div>
        <span
          className={
            "pkg-status-chip " +
            statusClass(rdl.missing_nets?.length ? "FAIL" : "PROXY")
          }
        >
          {routed.size}/{nets.length || "—"} nets
        </span>
      </div>
      <div className="pkg-rdl-list">
        {nets.length ? (
          nets.map((net) => {
            const row = rowByNet.get(net);
            const isRouted = routed.has(net);
            return (
              <div className="pkg-rdl-row" key={net}>
                <span className={"pkg-rdl-dot " + (isRouted ? "ok" : "bad")} />
                <strong>{net}</strong>
                <span>{isRouted ? "routed" : "missing"}</span>
                <small>
                  {Array.isArray(row?.route_layers)
                    ? row.route_layers.join(" / ")
                    : "—"}{" "}
                  · {formatNumber(row?.route_length_um_est, 2)} µm
                </small>
              </div>
            );
          })
        ) : (
          <p className="pkg-manifest-empty-copy">
            No configured RDL nets are available.
          </p>
        )}
      </div>
      <div className="pkg-manifest-inline-metrics">
        <span>
          Layers <strong>{rdl.layers?.join(" / ") || "—"}</strong>
        </span>
        <span>
          Segments <strong>{rdl.route_segments ?? "—"}</strong>
        </span>
        <span>
          Length <strong>{formatNumber(rdl.route_length_um_est, 2)} µm</strong>
        </span>
      </div>
    </section>
  );
}

function Provenance({ manifest }: { manifest: PackageManifest }) {
  const artifacts = manifest.provenance?.artifacts || [];
  return (
    <section className="pkg-manifest-section pkg-manifest-provenance">
      <div className="pkg-manifest-section-head">
        <div>
          <span className="pkg-section-kicker">Reproducibility</span>
          <h3>Live inputs and generated artifacts</h3>
        </div>
        <code>{shortHash(manifest.provenance?.input_fingerprint)}</code>
      </div>
      <ul>
        {artifacts.map((artifact, index) => (
          <li key={(artifact.role || "artifact") + "-" + index}>
            <span
              className={
                artifact.exists ? "artifact-present" : "artifact-missing"
              }
            >
              {artifact.exists ? "●" : "○"}
            </span>
            <strong>{artifact.role || "artifact"}</strong>
            <span className="pkg-artifact-path">
              {artifact.path || "path unavailable"}
            </span>
            <code>{shortHash(artifact.sha256)}</code>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function PackageManifestPanel({
  manifest,
  view = "overview",
}: {
  manifest?: PackageManifest | null;
  view?: ManifestView;
}) {
  if (!manifest) {
    return (
      <section className="pkg-manifest-panel pkg-manifest-empty">
        <div>
          <span className="pkg-section-kicker">Live package manifest</span>
          <h2>PKG evidence is not available for this finish</h2>
          <p>
            The package surface will show geometry, connectivity and
            provenance only after a current finish snapshot is registered.
          </p>
        </div>
        <span className="pkg-status-chip warn">GAP · NOT RUN</span>
      </section>
    );
  }

  const die = manifest.interface?.die || {};
  const bump = manifest.bump_array || {};
  const electrical = manifest.electrical_model || {};
  const pdn = manifest.system_pdn || {};
  const dieWidth = numberValue(die.width_um);
  const dieHeight = numberValue(die.height_um);
  const dieArea =
    dieWidth != null && dieHeight != null ? dieWidth * dieHeight : null;
  const effectiveLNh = numberValue(electrical.effective_supply_l_h);
  const requiredCount = manifest.rdl?.required_nets?.length || 0;
  const routedCount = manifest.rdl?.routed_nets?.length || 0;
  const coverage =
    requiredCount > 0 ? routedCount + "/" + requiredCount : "—";

  return (
    <section className="pkg-manifest-panel" aria-label="Live package manifest">
      <header className="pkg-manifest-head">
        <div>
          <span className="pkg-section-kicker">Live package manifest</span>
          <h2>
            {manifest.variant || "selected finish"}{" "}
            <span className="pkg-manifest-stage">
              · finish → package boundary
            </span>
          </h2>
          <p>{manifest.summary || "Package interface evidence loaded."}</p>
        </div>
        <div className="pkg-manifest-status">
          <span
            className={"pkg-status-chip " + statusClass(manifest.status)}
          >
            {statusText(manifest.status)}
          </span>
          <small>
            {manifest.evidence_ok
              ? "evidence current"
              : "evidence incomplete"}
          </small>
        </div>
      </header>

      <StatusRail manifest={manifest} />

      <div className="pkg-manifest-metrics">
        <Metric
          label="Die envelope"
          value={
            dieWidth != null && dieHeight != null
              ? formatNumber(dieWidth) +
                " × " +
                formatNumber(dieHeight) +
                " µm"
              : "—"
          }
          detail={dieArea != null ? formatNumber(dieArea) + " µm²" : undefined}
          tone="accent"
        />
        <Metric
          label="Bump map"
          value={
            String(bump.configured_count ?? "—") +
            " / " +
            String(bump.observed_component_count ?? "—")
          }
          detail="configured / observed components"
        />
        <Metric
          label="RDL coverage"
          value={coverage}
          detail={
            String(manifest.rdl?.route_segments ?? "—") + " route segments"
          }
          tone={
            routedCount === requiredCount && requiredCount > 0 ? "ok" : "warn"
          }
        />
        <Metric
          label="System droop"
          value={formatNumber(pdn.droop_mv) + " mV"}
          detail={formatNumber(pdn.droop_pct) + "% of VDD"}
          tone="ok"
        />
        <Metric
          label="Zmax"
          value={formatNumber(pdn.z_max_mohm) + " mΩ"}
          detail={
            pdn.f_at_zmax_hz
              ? "@ " + formatNumber(pdn.f_at_zmax_hz, 0) + " Hz"
              : undefined
          }
        />
        <Metric
          label="Package R / L"
          value={formatNumber(electrical.effective_supply_r_ohm, 3) + " Ω"}
          detail={
            formatNumber(effectiveLNh == null ? null : effectiveLNh * 1e9, 3) +
            " nH · " +
            String(electrical.n_supply_bumps ?? "—") +
            " modeled supply bumps · resonance " +
            formatNumber(electrical.series_resonance_hz_est, 0) +
            " Hz"
          }
        />
      </div>

      {view !== "connectivity" && <BumpMap manifest={manifest} />}

      {view !== "geometry" && <RdlConnectivity manifest={manifest} />}

      <section className="pkg-manifest-boundary">
        <div>
          <span className="pkg-section-kicker">Boundary condition</span>
          <h3>Product signoff remains closed</h3>
          <p>
            This is live package evidence on a dummy bump/RDL sidecar and a
            compact lumped RLC model. It does not create a Product badge.
          </p>
        </div>
        <div className="pkg-boundary-tags">
          {Object.entries(manifest.limits || {}).map(([key, value]) => (
            <span key={key} title={value}>
              {key.replaceAll("_", " ")}
            </span>
          ))}
          <strong>product_signoff = false</strong>
        </div>
      </section>

      {view === "overview" && <Provenance manifest={manifest} />}
    </section>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Circle, XCircle } from "lucide-react";

type Gate = {
  id: string;
  pillar: string;
  label: string;
  ok: boolean;
  detail?: string;
  action?: string;
};

type CheckEval = {
  id: string;
  label: string;
  actual: unknown;
  target: unknown;
  ok: boolean;
  note?: string;
};

type ArtifactParse = {
  exists?: boolean;
  items?: number;
  samples?: { category: string; detail: string }[];
  categories?: string[];
  lvsdb?: { exists?: boolean; errors?: number; must_connect?: number; messages?: string[] };
  log?: { exists?: boolean; tail?: string[]; missing_lylvs?: boolean; netlists_match?: boolean };
};

type PillarRow = {
  id: string;
  label: string;
  description: string;
  orchestratorAction: string;
  status?: string;
  reportEval?: {
    ok?: boolean;
    summary?: string;
    checks: CheckEval[];
    artifactParse?: ArtifactParse;
  } | null;
};

type StaIr = {
  ok?: boolean;
  slack_ns?: number | null;
  slack_ir_ns?: number | null;
  n_joined?: number | null;
  n_gates?: number | null;
  degradation_ps?: number | null;
};

type EcoInfo = {
  ok?: boolean;
  mode?: string;
  summary?: string;
  signoff?: boolean;
};

type SignoffApi = {
  variant: string;
  evaluation: { ok: boolean; gates: Gate[] };
  pillars: PillarRow[];
  plannedPillars?: PillarRow[];
  orchestrator: { action: string; label: string; reportExists: boolean };
  staIr?: StaIr | null;
  eco?: EcoInfo | null;
};

function StatusIcon({ ok, pending }: { ok: boolean; pending?: boolean }) {
  if (pending) return <Circle size={16} className="sig-pending" aria-hidden />;
  return ok ? (
    <CheckCircle2 size={16} className="sig-ok" aria-hidden />
  ) : (
    <XCircle size={16} className="sig-fail" aria-hidden />
  );
}

function leftoverCircuits(messages?: string[]): string[] {
  return Array.from(
    new Set(
      (messages || [])
        .map((m) => m.match(/circuit (\S+)/)?.[1])
        .filter((n): n is string => Boolean(n)),
    ),
  );
}

function ArtifactDetails({ pillarId, parse }: { pillarId: string; parse?: ArtifactParse }) {
  if (!parse) return null;
  if (pillarId === "geometry" && parse.exists) {
    return (
      <div className="sig-artifact">
        <strong>DRC .lyrdb</strong>
        <p>
          Violations: {parse.items ?? 0}
          {parse.categories && parse.categories.length > 0 && (
            <> · categories: {parse.categories.slice(0, 4).join(", ")}</>
          )}
        </p>
        {parse.samples && parse.samples.length > 0 && (
          <ul>
            {parse.samples.slice(0, 4).map((s, i) => (
              <li key={i}>
                <code>{s.category}</code> {s.detail}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  if (pillarId === "equivalence" && parse.lvsdb) {
    const lvs = parse.lvsdb;
    const log = parse.log;
    const leftover = leftoverCircuits(lvs.messages);
    return (
      <div className="sig-artifact">
        <strong>LVS report</strong>
        <p>
          {lvs.exists ? (
            <>
              Errors: {lvs.errors ?? 0}
              {log?.netlists_match === true && <> · netlists match</>}
              {log?.netlists_match === false && <> · netlists don&apos;t match</>}
              {typeof lvs.must_connect === "number" && lvs.must_connect > 0 && (
                <>
                  {" "}
                  · must-connect {lvs.must_connect}
                  {leftover.length ? ` (${leftover.join(", ")})` : ""}
                </>
              )}
            </>
          ) : (
            <>Missing .lvsdb file</>
          )}
          {log?.missing_lylvs && <> · missing .lylvs runset</>}
        </p>
        {lvs.messages && lvs.messages.length > 0 && (
          <ul>
            {lvs.messages.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        )}
        {log?.tail && log.tail.length > 0 && (
          <pre className="sig-log-tail">{log.tail.slice(-6).join("\n")}</pre>
        )}
      </div>
    );
  }
  return null;
}

function fmtVal(v: unknown): string {
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3);
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v ?? "—");
}

export function SignoffMatrixPanel({
  variant = "flowlab",
  busy,
  onRun,
  showOrchestrator = true,
}: {
  variant?: string;
  busy?: string | null;
  onRun?: (action: string, long: boolean) => void;
  showOrchestrator?: boolean;
}) {
  const [data, setData] = useState<SignoffApi | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`/api/signoff?variant=${encodeURIComponent(variant)}`);
      if (!res.ok) throw new Error(`signoff ${res.status}`);
      setData(await res.json());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Signoff error");
    }
  }, [variant]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const pillarGates =
    data?.evaluation.gates.filter((g) =>
      data.pillars.some((p) => p.id === g.id),
    ) ?? [];
  const allGate = data?.evaluation.gates.find((g) => g.id === "signoff_all");

  return (
    <div className="sig-matrix">
      <div className="sig-matrix-head">
        <strong>GCD signoff matrix</strong>
        <p>
          4 active pillars vs{" "}
          <a href="/materials/reference/signoff-matrix.md">golden-gcd.json</a>
          {data && (
            <>
              {" "}
              · variant <code>{data.variant}</code>
            </>
          )}
        </p>
        {err && <p className="sig-err">{err}</p>}
      </div>

      <ul className="sig-pillar-list">
        {pillarGates.map((g) => {
          const pillar = data?.pillars.find((p) => p.id === g.id);
          const action = pillar?.orchestratorAction ?? g.action;
          const long =
            action === "drc_signoff" ||
            action === "klayout_lvs" ||
            action === "power_signoff";
          const checks = pillar?.reportEval?.checks ?? [];
          const isOpen = expanded === g.id;
          return (
            <li key={g.id} className={g.ok ? "sig-row-ok" : "sig-row-fail"}>
              <StatusIcon ok={g.ok} pending={!g.detail?.includes("·") && !g.ok && !checks.length} />
              <div className="sig-row-body">
                <strong>{g.label}</strong>
                <small>{g.detail}</small>
                {g.id === "timing" && data?.staIr && (
                  <small>
                    IR-aware slack {data.staIr.slack_ns?.toFixed(4) ?? "—"} →{" "}
                    {data.staIr.slack_ir_ns?.toFixed(4) ?? "—"} ns
                    {data.staIr.n_joined != null && data.staIr.n_gates != null
                      ? ` · ${data.staIr.n_joined}/${data.staIr.n_gates} gates`
                      : ""}
                  </small>
                )}
                {(checks.length > 0 || pillar?.reportEval?.artifactParse) && (
                  <button
                    type="button"
                    className="sig-expand-btn"
                    onClick={() => setExpanded(isOpen ? null : g.id)}
                  >
                    {isOpen ? "Hide details" : "Metrics & artifacts"}
                  </button>
                )}
                {isOpen && checks.length > 0 && (
                  <table className="sig-check-table">
                    <thead>
                      <tr>
                        <th>Check</th>
                        <th>Actual</th>
                        <th>Target</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {checks.map((c) => (
                        <tr key={c.id} className={c.ok ? "sig-check-ok" : "sig-check-fail"}>
                          <td>{c.label}</td>
                          <td>{fmtVal(c.actual)}</td>
                          <td>{fmtVal(c.target)}</td>
                          <td>{c.ok ? "✓" : "✗"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {isOpen && (g.id === "geometry" || g.id === "equivalence") && (
                  <ArtifactDetails
                    pillarId={g.id}
                    parse={
                      g.id === "equivalence"
                        ? (pillar?.reportEval?.artifactParse as ArtifactParse | undefined)
                        : pillar?.reportEval?.artifactParse
                    }
                  />
                )}
              </div>
              {onRun && action && (
                <button
                  type="button"
                  className="sig-run-btn"
                  disabled={Boolean(busy)}
                  onClick={() => onRun(action, long)}
                >
                  {busy === action ? "…" : "Run"}
                </button>
              )}
            </li>
          );
        })}
      </ul>

      {data?.plannedPillars && data.plannedPillars.length > 0 && (
        <div className="sig-planned">
          <strong>Phase 2 (HotSpot + dummy RDL)</strong>
          <ul className="sig-pillar-list">
            {data.plannedPillars.map((p) => {
              const eval_ = p.reportEval;
              const ok = eval_?.ok;
              const action = p.orchestratorAction;
              const canRun = action === "thermal_signoff" || action === "pkg_signoff";
              const checks = eval_?.checks ?? [];
              const isOpen = expanded === p.id;
              return (
                <li key={p.id} className={ok === true ? "sig-row-ok" : ok === false ? "sig-row-fail" : ""}>
                  <StatusIcon ok={Boolean(ok)} pending={!eval_} />
                  <div className="sig-row-body">
                    <strong>
                      {p.status && p.status !== "active" ? (
                        <span className="sig-planned-badge">{p.status}</span>
                      ) : null}{" "}
                      {p.label}
                    </strong>
                    <small>{eval_?.summary ?? p.description}</small>
                    {checks.length > 0 && (
                      <button
                        type="button"
                        className="sig-expand-btn"
                        onClick={() => setExpanded(isOpen ? null : p.id)}
                      >
                        {isOpen ? "Hide details" : "Metrics"}
                      </button>
                    )}
                    {isOpen && checks.length > 0 && (
                      <table className="sig-check-table">
                        <thead>
                          <tr>
                            <th>Check</th>
                            <th>Actual</th>
                            <th>Target</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {checks.map((c) => (
                            <tr key={c.id} className={c.ok ? "sig-check-ok" : "sig-check-fail"}>
                              <td>{c.label}</td>
                              <td>{fmtVal(c.actual)}</td>
                              <td>{fmtVal(c.target)}</td>
                              <td>{c.ok ? "✓" : "✗"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                  {onRun && canRun && (
                    <button
                      type="button"
                      className="sig-run-btn"
                      disabled={Boolean(busy)}
                      onClick={() => onRun(action, action === "pkg_signoff")}
                    >
                      {busy === action ? "…" : "Run"}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {showOrchestrator && onRun && (
        <div className="sig-orch-row">
          {allGate && (
            <button
              type="button"
              className="sig-all-btn"
              disabled={Boolean(busy)}
              onClick={() => onRun("signoff_all", true)}
            >
              {busy === "signoff_all" ? "Full signoff…" : "Full signoff (STA→DRC→LVS→Power)"}
            </button>
          )}
          <button
            type="button"
            className="sig-all-btn sig-phase2-btn"
            disabled={Boolean(busy)}
            onClick={() => onRun("signoff_phase2", false)}
          >
            {busy === "signoff_phase2" ? "Phase 2…" : "Signoff Phase 2 (thermal + PKG)"}
          </button>
        </div>
      )}

      {data?.eco && (
        <p className="sig-summary">
          ECO {data.eco.mode ?? "propose"}: {data.eco.summary ?? "—"}
          {data.eco.signoff ? " · claims signoff (bug)" : " · does not claim signoff"}
        </p>
      )}

      {data && (
        <p className="sig-summary">
          Global status:{" "}
          <span className={data.evaluation.ok ? "sig-ok-text" : "sig-fail-text"}>
            {data.evaluation.ok ? "PASS" : "FAIL / incomplete"}
          </span>
        </p>
      )}
    </div>
  );
}

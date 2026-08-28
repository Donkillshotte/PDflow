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

type PillarRow = {
  id: string;
  label: string;
  description: string;
  orchestratorAction: string;
  status?: string;
  reportEval?: { ok?: boolean; summary?: string; checks: CheckEval[] } | null;
};

type SignoffApi = {
  variant: string;
  evaluation: { ok: boolean; gates: Gate[] };
  pillars: PillarRow[];
  plannedPillars?: PillarRow[];
  orchestrator: { action: string; label: string; reportExists: boolean };
};

function StatusIcon({ ok, pending }: { ok: boolean; pending?: boolean }) {
  if (pending) return <Circle size={16} className="sig-pending" aria-hidden />;
  return ok ? (
    <CheckCircle2 size={16} className="sig-ok" aria-hidden />
  ) : (
    <XCircle size={16} className="sig-fail" aria-hidden />
  );
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
      setErr(e instanceof Error ? e.message : "Errore signoff");
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
        <strong>Matrice signoff GCD</strong>
        <p>
          4 pilastri attivi vs{" "}
          <a href="/materiali/reference/signoff-matrix.md">golden-gcd.json</a>
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
                {checks.length > 0 && (
                  <button
                    type="button"
                    className="sig-expand-btn"
                    onClick={() => setExpanded(isOpen ? null : g.id)}
                  >
                    {isOpen ? "Nascondi metriche" : "Metriche golden"}
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
          <strong>Fase 2 (planned)</strong>
          <ul>
            {data.plannedPillars.map((p) => (
              <li key={p.id}>
                <span className="sig-planned-badge">planned</span> {p.label} — {p.description}
              </li>
            ))}
          </ul>
        </div>
      )}

      {showOrchestrator && allGate && onRun && (
        <button
          type="button"
          className="sig-all-btn"
          disabled={Boolean(busy)}
          onClick={() => onRun("signoff_all", true)}
        >
          {busy === "signoff_all" ? "Signoff completo…" : "Signoff completo (STA→DRC→LVS→Power)"}
        </button>
      )}

      {data && (
        <p className="sig-summary">
          Stato globale:{" "}
          <span className={data.evaluation.ok ? "sig-ok-text" : "sig-fail-text"}>
            {data.evaluation.ok ? "PASS" : "FAIL / incompleto"}
          </span>
        </p>
      )}
    </div>
  );
}

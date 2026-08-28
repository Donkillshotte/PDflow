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

type SignoffApi = {
  variant: string;
  evaluation: { ok: boolean; gates: Gate[] };
  pillars: { id: string; label: string; description: string; orchestratorAction: string }[];
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
          4 pilastri vs{" "}
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
          const long = action === "drc_signoff" || action === "klayout_lvs" || action === "power_signoff";
          return (
            <li key={g.id} className={g.ok ? "sig-row-ok" : "sig-row-fail"}>
              <StatusIcon ok={g.ok} pending={!g.detail?.includes("report") && !g.ok} />
              <div className="sig-row-body">
                <strong>{g.label}</strong>
                <small>{g.detail}</small>
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

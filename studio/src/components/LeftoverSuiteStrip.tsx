"use client";

import { useEffect, useState } from "react";
import { LeftoverChips } from "@/components/LeftoverChips";
import { leftoverLabel, leftoverNamedIds } from "@/lib/leftoverUi";

type SuiteHook = {
  leftover?: { ids?: string[] };
};

type SuitePayload = {
  leftover?: { ids?: string[] };
  hooks?: SuiteHook[];
};

function leftoverIdsFromSuite(payload: SuitePayload): string[] {
  const collected: string[] = [];
  for (const id of payload.leftover?.ids ?? []) collected.push(id);
  for (const hook of payload.hooks ?? []) {
    for (const id of hook.leftover?.ids ?? []) collected.push(id);
  }
  return leftoverNamedIds(collected);
}

export function LeftoverSuiteStrip({
  compact = false,
  href = "/tools#suite",
}: {
  compact?: boolean;
  href?: string;
}) {
  const [ids, setIds] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/suite")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((payload: SuitePayload) => {
        if (cancelled) return;
        setError(null);
        setIds(leftoverIdsFromSuite(payload));
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "suite unavailable");
        setIds([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (ids === null) {
    return (
      <p className="muted leftover-suite-strip-fallback">
        Loading leftover named…
      </p>
    );
  }

  if (error) {
    return (
      <p className="muted leftover-suite-strip-fallback leftover-suite-strip-error">
        Leftover named could not load ({error}). Open the{" "}
        <a href="/tools#suite">suite</a> or{" "}
        <a href="/flow?phase=finish#signoff">finish signoff</a>.
      </p>
    );
  }

  if (!ids.length) {
    return (
      <p className="muted leftover-suite-strip-fallback">
        Leftover named: STA, DRC, LVS, IR, thermal, PKG, and DSE stay on their
        own hooks. Open the <a href="/tools#suite">suite</a> or{" "}
        <a href="/flow?phase=finish#signoff">finish signoff</a>.
      </p>
    );
  }

  return (
    <div className="leftover-suite-strip">
      <p className="leftover-suite-strip-head">
        <a href={href}>{ids.length} leftover named</a>
      </p>
      <LeftoverChips ids={ids} compact={compact} href={href} />
      <p className="muted leftover-suite-strip-note">
        Live from <code>/api/suite</code>.{" "}
        {ids.slice(0, 3).map((id) => leftoverLabel(id)).join(" · ")}
        {ids.length > 3 ? " · …" : ""}.
      </p>
    </div>
  );
}

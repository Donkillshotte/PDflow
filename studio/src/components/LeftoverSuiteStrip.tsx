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
  // Render a useful, non-blocking fallback immediately.  This strip is
  // auxiliary UI and must not hold the FlowLab hero in a loading state while
  // a cold Next development server compiles /api/suite.
  const [ids, setIds] = useState<string[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let retry: number | null = null;
    let attempt = 0;
    let requestTimer: number | null = null;

    const load = () => {
      const controller = new AbortController();
      // A cold Next dev compile can take longer than a normal API response.
      // Keep the UI bounded while avoiding a false fallback during startup.
      requestTimer = window.setTimeout(() => controller.abort(), 30000);
      fetch("/api/suite", { cache: "no-store", signal: controller.signal })
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then((payload: SuitePayload) => {
          if (cancelled) return;
          attempt = 0;
          setError(null);
          setLoadState("ready");
          setIds(leftoverIdsFromSuite(payload));
        })
        .catch((e: unknown) => {
          if (cancelled) return;
          const errorMessage =
            e instanceof Error && e.name === "AbortError"
              ? "suite request timed out"
              : e instanceof Error
                ? e.message
                : "suite unavailable";
          setError(errorMessage);
          setLoadState("error");
          setIds([]);
          attempt += 1;
          retry = window.setTimeout(load, Math.min(5000, 750 * 2 ** Math.min(attempt - 1, 3)));
        })
        .finally(() => {
          if (requestTimer !== null) {
            window.clearTimeout(requestTimer);
            requestTimer = null;
          }
        });
    };

    load();
    return () => {
      cancelled = true;
      if (retry !== null) window.clearTimeout(retry);
      if (requestTimer !== null) window.clearTimeout(requestTimer);
    };
  }, []);

  if (!ids.length) {
    return (
      <p className="muted leftover-suite-strip-fallback" role="status" aria-live="polite">
        {loadState === "error"
          ? `Suite status is temporarily unavailable${error ? ` (${error})` : ""}. `
          : "Checking live suite hooks. "}
        Leftover status is detailed on the <a href="/tools#suite">suite</a> and{" "}
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

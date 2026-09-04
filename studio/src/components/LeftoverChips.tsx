"use client";

import clsx from "clsx";
import {
  leftoverIdsFromText,
  leftoverLabel,
  leftoverNamedIds,
  leftoverTone,
} from "@/lib/leftoverUi";

export function LeftoverChips({
  ids,
  detail,
  compact,
}: {
  ids?: string[];
  detail?: string | null;
  compact?: boolean;
}) {
  const fromIds = leftoverNamedIds(ids);
  const fromDetail = leftoverNamedIds(leftoverIdsFromText(detail));
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const id of [...fromIds, ...fromDetail]) {
    if (seen.has(id)) continue;
    seen.add(id);
    ordered.push(id);
  }
  if (!ordered.length) return null;
  return (
    <ul
      className={clsx("leftover-chips", compact && "leftover-chips-compact")}
      aria-label="Named leftovers"
    >
      {ordered.map((id) => (
        <li key={id} className={clsx("leftover-chip", leftoverTone(id))}>
          {leftoverLabel(id)}
        </li>
      ))}
    </ul>
  );
}

export function StatusTone({
  state,
  okLabel = "ok",
  leftoverLabelText = "leftover",
  gapLabel = "gap",
}: {
  state: "ok" | "leftover" | "gap";
  okLabel?: string;
  leftoverLabelText?: string;
  gapLabel?: string;
}) {
  const text =
    state === "leftover" ? leftoverLabelText : state === "gap" ? gapLabel : okLabel;
  return <span className={clsx("pill", state === "ok" ? "ok" : state)}>{text}</span>;
}

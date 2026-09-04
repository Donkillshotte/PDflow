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
  href,
}: {
  ids?: string[];
  detail?: string | null;
  compact?: boolean;
  href?: string;
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
  const cap = compact ? 8 : 16;
  const shown = ordered.slice(0, cap);
  const extra = ordered.length - shown.length;
  const list = (
    <ul
      className={clsx("leftover-chips", compact && "leftover-chips-compact")}
      aria-label="Named leftovers"
    >
      {shown.map((id) => (
        <li
          key={id}
          className={clsx("leftover-chip", leftoverTone(id))}
          title={id}
        >
          {leftoverLabel(id)}
        </li>
      ))}
      {extra > 0 && (
        <li className="leftover-chip leftover-chip-more" title={`${extra} more leftover named`}>
          +{extra} more
        </li>
      )}
    </ul>
  );
  if (!href) return list;
  return (
    <a href={href} className="leftover-chips-link">
      {list}
    </a>
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

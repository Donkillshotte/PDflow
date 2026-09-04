"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const SURFACES = [
  {
    id: "course",
    label: "Course",
    href: "/flow",
    note: "FlowLab · leftover named",
    match: (p: string) =>
      p === "/" ||
      p.startsWith("/flow") ||
      p.startsWith("/lessons") ||
      p.startsWith("/materials") ||
      p.startsWith("/tools"),
  },
  {
    id: "lab",
    label: "Lab",
    href: "/lab",
    note: "Proposer · not signoff",
    match: (p: string) => p.startsWith("/lab"),
  },
  {
    id: "product",
    label: "Product",
    href: "/product",
    note: "win_rule.py",
    match: (p: string) => p.startsWith("/product"),
  },
] as const;

export function SurfaceRail({ compact }: { compact?: boolean }) {
  const pathname = usePathname() ?? "/";
  return (
    <nav
      className={clsx("surface-rail", compact && "surface-rail-compact")}
      aria-label="Three surfaces"
    >
      {SURFACES.map((s) => {
        const active = s.match(pathname);
        return (
          <Link
            key={s.id}
            href={s.href}
            className={clsx("surface-rail-item", active && "is-active")}
            aria-current={active ? "page" : undefined}
          >
            <strong>{s.label}</strong>
            {!compact && <em>{s.note}</em>}
          </Link>
        );
      })}
      <Link href="/pkg" className="surface-rail-item surface-rail-pkg">
        <strong>PKG</strong>
        {!compact && <em>after signoff</em>}
      </Link>
    </nav>
  );
}

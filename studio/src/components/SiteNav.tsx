"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const LINKS = [
  { href: "/", label: "Studio" },
  { href: "/flow", label: "Flow" },
  { href: "/pkg", label: "PKG" },
  { href: "/lessons", label: "Lessons" },
  { href: "/tools", label: "Tools" },
  { href: "/materials", label: "Materials" },
];

export function SiteNav() {
  const pathname = usePathname();
  return (
    <header className="site-nav">
      <Link href="/" className="brand-mark">
        <span className="brand-word">OpenROAD</span>
        <span className="brand-sub">Physical Design Studio</span>
      </Link>
      <nav className="nav-links" aria-label="Main">
        {LINKS.map((l) => {
          const active =
            l.href === "/"
              ? pathname === "/"
              : pathname === l.href || pathname.startsWith(l.href + "/");
          return (
            <Link
              key={l.href}
              href={l.href}
              className={clsx("nav-link", active && "nav-link-active")}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { SurfaceRail } from "./SurfaceRail";

const GROUPS = [
  {
    label: "Course",
    links: [
      { href: "/", label: "Studio" },
      { href: "/flow", label: "Flow" },
      { href: "/lessons", label: "Lessons" },
      { href: "/materials", label: "Materials" },
    ],
  },
  {
    label: "Lab",
    links: [{ href: "/lab", label: "Lab" }],
  },
  {
    label: "Product",
    links: [{ href: "/product", label: "Product" }],
  },
  {
    label: "After",
    links: [
      { href: "/pkg", label: "PKG" },
      { href: "/tools", label: "Tools" },
    ],
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteNav() {
  const pathname = usePathname() ?? "/";
  return (
    <header className="site-nav">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <Link href="/" className="brand-mark">
        <span className="brand-word">OpenROAD</span>
        <span className="brand-sub">Physical Design Studio</span>
      </Link>
      <nav className="nav-groups" aria-label="Main">
        {GROUPS.map((g) => (
          <div key={g.label} className="nav-group">
            <span className="nav-group-label">{g.label}</span>
            <div className="nav-links">
              {g.links.map((l) => (
                <Link
                  key={l.href}
                  href={l.href}
                  className={clsx("nav-link", isActive(pathname, l.href) && "nav-link-active")}
                >
                  {l.label}
                </Link>
              ))}
            </div>
          </div>
        ))}
        <Link href="/flow?phase=finish#signoff" className="nav-leftover-link">
          leftover named
        </Link>
      </nav>
      <SurfaceRail compact />
    </header>
  );
}

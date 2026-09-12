"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  BookOpen,
  Box,
  FileText,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  Workflow,
  Wrench,
} from "lucide-react";

const WORKSPACES = [
  { href: "/", label: "Overview", note: "Current invocation", Icon: LayoutDashboard },
  { href: "/product", label: "Product", note: "Signoff oracle", Icon: Gauge },
  { href: "/flow", label: "FlowLab", note: "RTL → GDSII", Icon: Workflow },
  { href: "/pkg", label: "Package", note: "Read-only system PDN", Icon: Box },
  { href: "/lab", label: "Lab", note: "DSE · experiments", Icon: FlaskConical },
  { href: "/tools", label: "Tools", note: "Registry · jobs", Icon: Wrench },
] as const;

const REFERENCES = [
  { href: "/lessons", label: "Lessons", Icon: BookOpen },
  { href: "/materials", label: "Materials", Icon: FileText },
] as const;

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteNav({
  collapsed = false,
  onToggle,
  flowHref = "/flow",
}: {
  collapsed?: boolean;
  onToggle?: () => void;
  flowHref?: string;
}) {
  const pathname = usePathname() ?? "/";
  return (
    <header className={clsx("site-nav", collapsed && "is-collapsed")} aria-label="PDflow application navigation">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <Link href="/" className="brand-mark">
        <span className="brand-lockup">
          <span className="brand-symbol" aria-hidden="true">PD</span>
          <span>
            <span className="brand-word">PDflow</span>
            <span className="brand-sub">Physical Design Studio</span>
          </span>
        </span>
      </Link>
      {onToggle && (
        <button
          type="button"
          className="nav-collapse-button"
          onClick={onToggle}
          aria-label={collapsed ? "Expand application navigation" : "Collapse application navigation"}
          title={collapsed ? "Expand navigation" : "Collapse navigation"}
        >
          {collapsed ? <PanelLeftOpen size={16} aria-hidden="true" /> : <PanelLeftClose size={16} aria-hidden="true" />}
          <span>{collapsed ? "Expand" : "Collapse"}</span>
        </button>
      )}
      <span className="nav-section-label">Workspace</span>
      <nav className="nav-app-links" aria-label="Workspace">
        {WORKSPACES.map(({ href, label, note, Icon }) => {
          const active = isActive(pathname, href);
          const targetHref = href === "/flow" ? flowHref : href;
          return (
            <Link
              key={href}
              href={targetHref}
              className={clsx("nav-app-link", active && "is-active")}
              aria-current={active ? "page" : undefined}
            >
              <Icon size={16} strokeWidth={1.8} aria-hidden />
              <span>
                <strong>{label}</strong>
                <small>{note}</small>
              </span>
            </Link>
          );
        })}
      </nav>
      <span className="nav-section-label nav-section-secondary">Reference</span>
      <nav className="nav-reference-links" aria-label="Reference">
        {REFERENCES.map(({ href, label, Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx("nav-reference-link", isActive(pathname, href) && "is-active")}
          >
            <Icon size={15} aria-hidden />
            {label}
          </Link>
        ))}
      </nav>
      <div className="nav-sidebar-footer">
        <Link href="/flow?phase=finish#signoff" className="nav-leftover-link">
          <span className="nav-footer-dot" aria-hidden="true" />
          leftover named
        </Link>
        <span className="nav-kbd-hint" title="Command palette">
          <kbd>Ctrl</kbd>+<kbd>K</kbd> command palette
        </span>
      </div>
    </header>
  );
}

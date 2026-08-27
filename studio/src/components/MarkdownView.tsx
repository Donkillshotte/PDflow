"use client";

import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function slugifyHeading(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

function headingText(children: ReactNode): string {
  if (typeof children === "string") return children;
  if (Array.isArray(children)) return children.map(headingText).join("");
  if (children && typeof children === "object" && "props" in children) {
    return headingText((children as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

function makeHeading(level: 1 | 2 | 3 | 4) {
  return ({ children }: { children?: ReactNode }) => {
    const text = headingText(children);
    const id = slugifyHeading(text);
    if (level === 1) return <h1 id={id}>{children}</h1>;
    if (level === 2) return <h2 id={id}>{children}</h2>;
    if (level === 3) return <h3 id={id}>{children}</h3>;
    return <h4 id={id}>{children}</h4>;
  };
}

function rewriteImageSrc(src?: string) {
  if (!src) return src;
  if (src.startsWith("http") || src.startsWith("/api/")) return src;
  // gui-atlas relative ./gui-shots/foo.png → API content
  const cleaned = src.replace(/^\.\//, "").replace(/^\//, "");
  if (cleaned.includes("gui-shots/") || cleaned.endsWith(".png")) {
    const path = cleaned.startsWith("gui-shots/")
      ? `reference/${cleaned}`
      : cleaned.includes("reference/")
        ? cleaned
        : `reference/${cleaned}`;
    return `/api/content?path=${encodeURIComponent(path)}`;
  }
  return src;
}

export function MarkdownView({
  content,
  basePath,
}: {
  content: string;
  basePath?: string;
}) {
  return (
    <div className="md-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: makeHeading(1),
          h2: makeHeading(2),
          h3: makeHeading(3),
          h4: makeHeading(4),
          img: ({ src, alt }) => {
            const srcStr = typeof src === "string" ? src : undefined;
            let resolved = rewriteImageSrc(srcStr);
            if (
              basePath &&
              srcStr &&
              !srcStr.startsWith("http") &&
              !srcStr.startsWith("/api")
            ) {
              const joined = `${basePath.replace(/\/$/, "")}/${srcStr.replace(/^\.\//, "")}`;
              resolved = `/api/content?path=${encodeURIComponent(joined)}`;
            }
            return (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={resolved} alt={alt ?? ""} className="md-img" />
            );
          },
          a: ({ href, children }) => {
            if (href?.endsWith(".md")) {
              const path = href.replace(/^\.\//, "");
              return (
                <a href={`/materiali/${basePath ? basePath + "/" : ""}${path}`}>
                  {children}
                </a>
              );
            }
            if (href?.endsWith(".sp") && !href.startsWith("http")) {
              const cleaned = href.replace(/^\.\//, "").replace(/^learn\//, "");
              return (
                <a href={`/materiali/file/${cleaned}`}>{children}</a>
              );
            }
            return (
              <a href={href} target={href?.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

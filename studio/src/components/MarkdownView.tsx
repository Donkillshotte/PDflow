"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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

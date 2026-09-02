import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "fs";
import path from "path";
import { resolveLearnContent } from "@/lib/course";

export const dynamic = "force-dynamic";

const TEXT_EXT = new Set([".sp", ".json", ".log", ".csv", ".tcl", ".v", ".txt"]);

export default async function LabFilePage({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const { slug } = await params;
  const rel = slug.join("/");
  const abs = resolveLearnContent(rel);
  if (!abs) notFound();

  const ext = path.extname(abs).toLowerCase();
  if (!TEXT_EXT.has(ext)) notFound();

  const content = fs.readFileSync(abs, "utf8");
  const name = slug[slug.length - 1] ?? rel;
  const sizeKb = Math.round(fs.statSync(abs).size / 1024);

  return (
    <main>
      <header className="page-head">
        <div className="lesson-num">learn/{rel}</div>
        <h1>{name}</h1>
        <p>
          File lab · {sizeKb} KB ·{" "}
          <a href={`/api/content?path=${encodeURIComponent(rel)}`}>JSON API</a>
        </p>
      </header>
      <div className="lesson-actions">
        <Link href="/materials" className="btn-ghost">
          ← Materials
        </Link>
        <Link href="/pkg" className="btn-ghost">
          PKG hub
        </Link>
        {ext === ".sp" && (
          <a
            className="btn-primary"
            href={`/api/flowlab/download?kind=spice&path=${encodeURIComponent(rel)}`}
          >
            Download
          </a>
        )}
      </div>
      <section className="panel">
        <pre className="lab-file-view">{content}</pre>
      </section>
    </main>
  );
}

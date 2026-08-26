import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "fs";
import { resolveLearnContent } from "@/lib/course";
import { MarkdownView } from "@/components/MarkdownView";

export const dynamic = "force-dynamic";

export default async function MaterialDetailPage({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const { slug } = await params;
  const rel = slug.join("/");
  const abs = resolveLearnContent(rel);
  if (!abs || !rel.endsWith(".md")) notFound();

  const content = fs.readFileSync(abs, "utf8");
  const basePath = rel.includes("/")
    ? rel.slice(0, rel.lastIndexOf("/"))
    : "";

  return (
    <main>
      <header className="page-head">
        <div className="lesson-num">{rel}</div>
        <h1>{slug[slug.length - 1]?.replace(/\.md$/, "")}</h1>
        <p>Documento del corso · percorso learn/{rel}</p>
      </header>
      <div className="lesson-actions">
        <Link href="/materiali" className="btn-ghost">
          ← Materiali
        </Link>
      </div>
      <section className="panel">
        <MarkdownView content={content} basePath={basePath} />
      </section>
    </main>
  );
}

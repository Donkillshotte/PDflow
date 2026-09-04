import { Suspense } from "react";
import { redirect } from "next/navigation";
import { FlowLab } from "@/components/FlowLab";

export default async function FlowPage({
  searchParams,
}: {
  searchParams: Promise<{ phase?: string }>;
}) {
  const phase = (await searchParams).phase;
  if (phase === "pkg") {
    redirect("/pkg");
  }
  return (
    <main>
      <Suspense fallback={<div className="muted">Loading FlowLab…</div>}>
        <FlowLab />
      </Suspense>
    </main>
  );
}

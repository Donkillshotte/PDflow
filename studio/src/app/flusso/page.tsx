import { Suspense } from "react";
import { FlowLab } from "@/components/FlowLab";

export default function FlussoPage() {
  return (
    <main>
      <Suspense fallback={<div className="muted">Loading FlowLab…</div>}>
        <FlowLab />
      </Suspense>
    </main>
  );
}

import Link from "next/link";
import { LeftoverChips } from "@/components/LeftoverChips";
import { leftoverNamedIds } from "@/lib/leftoverUi";
import { getSuiteStatus } from "@/lib/suite";

/** Home shows counts only. The hook matrix stays on /tools#suite. */
export async function HomeOpsStrip() {
  let counts = "Toolchain status lives on Tools.";
  let leftoverIds: string[] = [];
  try {
    const suite = await getSuiteStatus();
    const s = suite.summary;
    leftoverIds = leftoverNamedIds(
      suite.hooks.flatMap((h) => h.leftover?.ids ?? []),
    );
    const leftoverN = leftoverIds.length;
    counts = `${s.hooksOk}/${s.hooksTotal} hooks ready · ${leftoverN} leftover named · pipeline ${s.pipelineReady}/6 · lessons ${s.lessonsDone}/${s.lessonsTotal}`;
    if (s.viewerRunning) counts += " · web viewer on";
  } catch {
    /* keep fallback */
  }

  return (
    <section className="panel home-suite" id="suite">
      <div className="home-rail-head">
        <h2 className="section-title">Toolchain</h2>
        <Link href="/tools#suite" className="home-rail-cta">
          Hook matrix
        </Link>
      </div>
      <p className="footer-note" style={{ marginTop: "0.5rem" }}>
        {counts}. Course, FlowLab, lab, and product keep their own contracts —
        this strip does not launch cooks.
      </p>
      <LeftoverChips ids={leftoverIds} compact />
    </section>
  );
}

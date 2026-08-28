"use client";

import { FlowLabLayoutCanvas } from "@/components/flowlab/FlowLabLayoutCanvas";

const STAGE_TO_PHASE: Record<
  string,
  "synth" | "floorplan" | "pdn" | "place" | "cts" | "route" | "finish" | "pkg"
> = {
  synth: "synth",
  floorplan: "floorplan",
  place: "place",
  cts: "cts",
  route: "route",
  finish: "finish",
};

/** Map lesson id + makeTarget to layout preview phase (learn variant). */
export function lessonLayoutPhase(
  lessonId: string,
  makeTarget: string,
):
  | "synth"
  | "floorplan"
  | "pdn"
  | "place"
  | "cts"
  | "route"
  | "finish"
  | "pkg"
  | null {
  if (lessonId === "03-floorplan") return "pdn";
  if (lessonId === "07-finish") return "finish";
  if (lessonId === "00-intro" || lessonId === "02-synthesis") return "synth";
  return STAGE_TO_PHASE[makeTarget] ?? null;
}

export function LessonLayoutPanel({
  lessonId,
  makeTarget,
  refreshKey,
}: {
  lessonId: string;
  makeTarget: string;
  refreshKey: number;
}) {
  const phase = lessonLayoutPhase(lessonId, makeTarget);
  if (!phase) return null;

  return (
    <div className="lesson-layout-panel">
      <FlowLabLayoutCanvas
        phaseId={phase}
        variant="learn"
        refreshKey={refreshKey}
        stageDone
      />
    </div>
  );
}

"use client";

import clsx from "clsx";
import {
  Box,
  Check,
  ChevronRight,
  Code2,
  Cpu,
  GitBranch,
  Layers,
  LayoutGrid,
  Lock,
  Loader2,
  Package,
  Route,
  Zap,
} from "lucide-react";
import type { Phase, StageStatus } from "./types";
import { PHASES, PHASE_IDS } from "./phases";

const ICONS = {
  code: Code2,
  cpu: Cpu,
  grid: LayoutGrid,
  box: Box,
  branch: GitBranch,
  route: Route,
  layers: Layers,
  zap: Zap,
  package: Package,
} as const;

function phaseUnlocked(id: string, stages: StageStatus[]) {
  const idx = PHASE_IDS.indexOf(id);
  if (idx <= 0) return true;
  const prev = PHASES[idx - 1];
  return Boolean(stages.find((s) => s.id === prev.id)?.done);
}

export function FlowLabPipeline({
  phases,
  phaseId,
  stages,
  running,
  onSelect,
}: {
  phases: Phase[];
  phaseId: string;
  stages: StageStatus[];
  running: boolean;
  onSelect: (id: string) => void;
}) {
  const activeIdx = PHASE_IDS.indexOf(phaseId);

  return (
    <nav className="fl-pipeline" aria-label="Pipeline RTL → GDSII">
      <ol className="fl-pipeline-track">
        {phases.map((p, i) => {
          const st = stages.find((s) => s.id === p.id);
          const open = phaseUnlocked(p.id, stages);
          const active = phaseId === p.id;
          const done = Boolean(st?.done);
          const Icon = ICONS[p.icon as keyof typeof ICONS] ?? Code2;
          const locked = !open && !done;

          return (
            <li key={p.id} className="fl-pipeline-step-wrap">
              {i > 0 && (
                <span
                  className={clsx(
                    "fl-pipeline-connector",
                    done && "fl-pipeline-connector-done",
                  )}
                  aria-hidden
                />
              )}
              <button
                type="button"
                disabled={locked}
                className={clsx(
                  "fl-pipeline-step",
                  active && "fl-pipeline-step-active",
                  done && "fl-pipeline-step-done",
                  locked && "fl-pipeline-step-locked",
                  running && active && "fl-pipeline-step-running",
                )}
                onClick={() => {
                  if (locked) return;
                  onSelect(p.id);
                }}
                aria-current={active ? "step" : undefined}
              >
                <span className="fl-pipeline-icon">
                  {running && active ? (
                    <Loader2 size={18} className="fl-spin" aria-hidden />
                  ) : done ? (
                    <Check size={18} strokeWidth={2.5} aria-hidden />
                  ) : locked ? (
                    <Lock size={16} aria-hidden />
                  ) : (
                    <Icon size={18} aria-hidden />
                  )}
                </span>
                <span className="fl-pipeline-text">
                  <span className="fl-pipeline-index">Fase {i + 1}</span>
                  <strong>{p.label}</strong>
                  <em>{p.hint}</em>
                </span>
                {active && (
                  <ChevronRight size={16} className="fl-pipeline-chevron" aria-hidden />
                )}
              </button>
            </li>
          );
        })}
      </ol>
      <div className="fl-pipeline-meta" aria-hidden>
        {activeIdx >= 0 && (
          <>
            <span>{phases[activeIdx]?.tool}</span>
            <span>·</span>
            <span>{phases[activeIdx]?.estTime}</span>
          </>
        )}
      </div>
    </nav>
  );
}

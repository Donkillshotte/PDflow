"use client";

import Link from "next/link";
import { powerLinkForLesson } from "@/lib/powerChainLessons";

export function LessonPowerChainPanel({ lessonId }: { lessonId: string }) {
  const link = powerLinkForLesson(lessonId);
  if (!link) return null;

  return (
    <aside className="lesson-power-chain" aria-label="Catena power e SPICE">
      <div className="lesson-power-chain-head">
        <strong>Catena power · {link.title}</strong>
        <Link href={`/materiali/reference/spice-power-chain.md#${link.anchor}`}>
          Guida completa
        </Link>
      </div>
      <p>{link.summary}</p>
      <div className="lesson-power-chain-grid">
        <div>
          <span className="lesson-power-k">FlowLab</span>
          <ul>
            {link.flowlabPhases.map((p) => (
              <li key={p}>
                <Link href={`/flusso?phase=${p}`}>{p}</Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <span className="lesson-power-k">ORFS / output</span>
          <ul>
            {link.orfsArtifacts.slice(0, 4).map((a) => (
              <li key={a}>
                <code>{a}</code>
              </li>
            ))}
          </ul>
        </div>
        {link.studioActions.length > 0 && (
          <div>
            <span className="lesson-power-k">Azioni Studio</span>
            <ul>
              {link.studioActions.map((a) => (
                <li key={a}>
                  <Link href={`/strumenti?tab=run&action=${a}`}>{a}</Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <div className="lesson-power-docs">
        {link.docs.map((d) => (
          <Link key={d.href} href={d.href}>
            {d.label}
          </Link>
        ))}
      </div>
    </aside>
  );
}

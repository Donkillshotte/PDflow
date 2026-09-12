# Evidence policy

Evidence is produced by the current local invocation, not copied from a
previous execution. Keep the command, environment, run id, input paths,
fingerprints, exit status, and report path together.

## Minimum evidence

| Area | Evidence |
|---|---|
| RTL → GDS | stage logs, ODB/DEF/GDS, SDC, SPEF |
| STA | current post-SPEF JSON and report path |
| Geometry | DRC/LVS output for the current artifacts |
| Power | activity source, mesh, solver output, scope |
| DSE | isolated JSONL memory and candidate provenance |
| UI | action id, job id, current report, visible state |

Use [`reference/live-analysis.md`](reference/live-analysis.md) as the review
checklist. A `GAP` is valid evidence of unavailable capability; it must never
be replaced by an older value. A report is not accepted as a comparison unless
its run identity and artifact fingerprints match.

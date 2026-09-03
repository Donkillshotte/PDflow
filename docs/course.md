# Course / Studio

RTL→GDS teaching. Does not decide product wins. ORFS variants `learn` and
`flowlab` are **locked**: the product wrapper refuses them.

## Course (`learn/`)

20–28 hour path: 8 lessons (00–07), LABs, Tcl walkthroughs, workbook, GUI.

```bash
./scripts/learn_physical_design.sh --check
./scripts/learn_physical_design.sh --list
./scripts/learn_physical_design.sh --deep --lesson 01-constraints
./scripts/test_course.sh
```

| File | Role |
|---|---|
| [`learn/README.md`](../learn/README.md) | Start here |
| [`learn/CURRICULUM.md`](../learn/CURRICULUM.md) | Syllabus |
| [`learn/EVIDENCE.md`](../learn/EVIDENCE.md) | Pipeline evidence |
| [`learn/AUDIT.md`](../learn/AUDIT.md) | Requirement-by-requirement |
| [`learn/reference/README.md`](../learn/reference/README.md) | Glossary, Tcl, IR, OSS |

GCD tutorial: `FLOW_VARIANT=learn`. Green finish ≠ timing closed
(see `golden-metrics.md`). Tutorial SDC 0.46 ns is aggressive.

## Studio (`studio/`)

Next.js UI. Orchestrates scripts with lock, phase dependencies, job history.

```bash
./scripts/run_studio.sh          # http://127.0.0.1:43217
./scripts/test_studio_api.sh
./scripts/test_all_phases.sh     # exhaustive
```

Details: [`studio/README.md`](../studio/README.md).
One ORFS job at a time (`learn/.studio-run.lock`).
FlowLab lives at `/flow`, `flowlab` variant isolated from the course.
Studio home (`/#story`) and `GET /api/story` stitch course, lab IR, STA
IR-aware slack, and product DSE into one path. They do not merge the
contracts. The Lab surface is `/lab` (physics ledger, DSE launch compare),
not FlowLab finish `#ir`.

OpenROAD Qt GUI: Desktop button on Cursor, not HTTP Preview cards.

## Course signoff

After `make finish` on the course variant:

```bash
export FLOW_VARIANT=learn   # locked for product; OK here
./learn/scripts/run_signoff_all.sh
```

Study power/IR chain: [`learn/reference/spice-power-chain.md`](../learn/reference/spice-power-chain.md).
Does not restamp gold 45.298 mV.

Educational closes on FlowLab (not product wins): gate VCD name-join,
dummy `rdl_route` on a sidecar ODB, HotSpot architecture °C, Xyce N4
dual-solver. Paths and leftovers: [`learn/reference/gap-close-paths.md`](../learn/reference/gap-close-paths.md).
CCS tables, Raphael/StarRC, Magic/Netgen without a FreePDK45 `.tech`,
and a fake LVS pass stay out of scope.

# Reference materials index

Estimated time **reference only**: 3–4 hours of active reading (not skimming).

## Recommended reading order

1. [glossary.md](./glossary.md) — keep open for the entire course
2. [file-formats.md](./file-formats.md) — lessons 00–01
3. [gui-atlas.md](./gui-atlas.md) — real Qt screenshots, pixel anatomy, gallery per phase
4. [gui-openroad.md](./gui-openroad.md) — menus, heatmap, Preview troubleshooting
5. [debug-playbook.md](./debug-playbook.md) — from lesson 03; required before lesson 05

## ORFS walkthrough scripts (read *while* running each phase)

| Phase | Document |
|---|---|
| Synthesis | [walkthrough-synth.tcl.md](./walkthrough-synth.tcl.md) |
| Floorplan | [walkthrough-floorplan.tcl.md](./walkthrough-floorplan.tcl.md) |
| Placement | [walkthrough-global_place.tcl.md](./walkthrough-global_place.tcl.md) |
| CTS | [walkthrough-cts.tcl.md](./walkthrough-cts.tcl.md) |
| Routing | [walkthrough-route.tcl.md](./walkthrough-route.tcl.md) |
| Finish | [walkthrough-finish.tcl.md](./walkthrough-finish.tcl.md) |

## Workbook and quiz

- [../workbook/README.md](../workbook/README.md) — exercises
- [../workbook/solutions.md](../workbook/solutions.md) — solutions (after trying)
- [../workbook/quiz.md](../workbook/quiz.md) — self-assessment per lesson
- [../workbook/notes-template.md](../workbook/notes-template.md) — notebook
- [../workbook/final-project-template.md](../workbook/final-project-template.md) — lesson 07 deliverable

## Tutorial run metrics

- [golden-metrics.md](./golden-metrics.md) — WNS/`period_min`/area/DRC measured on `FLOW_VARIANT=learn`

## Power · SPICE · phase linkage

After lessons 00–07, for end-to-end power integrity:

1. [spice-power-chain.md](./spice-power-chain.md) — **RTL→PKG chain** (read first)
2. [spice-chip-mesh.md](./spice-chip-mesh.md) — on-die mesh `write_pg_spice`
3. [vyges-em-ir.md](./vyges-em-ir.md) — Apache-2.0 IR/EM engine on the GCD mesh
4. [dynamic-ir.md](./dynamic-ir.md) — I(t) per pin + heatmap
5. [dynamic-ir-landscape.md](./dynamic-ir-landscape.md) — PDNSim / vyges / EMSim / ngspice
5b. [dse.md](./dse.md) — multi-fidelity DSE (e-graph + BOiLS SSK-GP + oracle IR)
4. [spice-ngspice-primer.md](./spice-ngspice-primer.md) — System PDN ngspice
5. [system-pdn.md](./system-pdn.md) — tool landscape
6. [pkg-design-package.md](./pkg-design-package.md) — packaging
7. [../sim/spice/README.md](../sim/spice/README.md) — local lab netlists

## Signoff · educational GAP closes

- [suite-status.md](./suite-status.md) — live WORKS / FAIL / GAP table for the whole flow
- [gaps.md](./gaps.md) — license/PDK gated vs to-build
- [signoff-matrix.md](./signoff-matrix.md) — pillars, Phase 2 (HotSpot + dummy RDL)
- [gap-close-paths.md](./gap-close-paths.md) — what is closable vs leftover on purpose
- [remaining-gaps-evaluation.md](./remaining-gaps-evaluation.md) — deep feasibility analysis of every remaining GAP
- [oss-integrations.md](./oss-integrations.md) — Icarus / HotSpot / Xyce / OpenRCX
- [extended-flow.md](./extended-flow.md) — Studio actions after `make finish`
- [tool-hooks.md](./tool-hooks.md) — `/api/suite` hook map

## GUI

- [gui-atlas.md](./gui-atlas.md) — pixel-level guide with PNGs in `gui-shots/`
- [gui-openroad.md](./gui-openroad.md) — panels, menus, 45 min sequence

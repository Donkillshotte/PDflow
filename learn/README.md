# Physical Design Course

This is the OpenROAD/ORFS RTL → GDS course. It uses a local Nangate45 flow and
keeps teaching, lab analysis, and product comparison as separate contracts.

## Start

```bash
./scripts/run_studio.sh
./scripts/learn_physical_design.sh --check
./scripts/learn_physical_design.sh --list
./scripts/learn_physical_design.sh --deep --lesson 03-floorplan
./scripts/test_course.sh
```

There are eight lessons (`00-intro` through `07-finish`), a LAB for each
stage, Tcl walkthroughs, a GUI atlas, and a workbook. Use the actual logs and
reports from your current run when filling exercises.

## Map

```text
learn/
├── lessons/       theory, LAB.md, run.sh
├── reference/     live-analysis contract, glossary, Tcl and GUI guides
├── workbook/      exercises, quiz and final project
├── designs/       tutorial RTL and constraints
└── scripts/       local runners and validation
```

The live-data policy is [`reference/live-analysis.md`](reference/live-analysis.md).
It requires a `run_id`, input fingerprints, and an explicit comparison scope;
missing data stays visible as `GAP` or `incomplete`.

## Studio surfaces

- `/flow` — FlowLab RTL-to-finish workbench.
- `/lab` — live DSE and physics.
- `/pkg` — packaging and phase-two analyses.
- `/tools` — direct tool actions and current job output.

For the native layout workflow, use the [GUI atlas](reference/gui-atlas.md):
it identifies the live ODB, the layer controls, and the browser-safe viewer
that mirrors the same artifact.

The UI updates from the report produced by the selected job. It does not
silently reuse a report from another execution.

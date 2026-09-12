# Curriculum

Every lesson follows Explain → Run → Inspect → Verify → Reflect. The learner
records metrics from the selected local invocation; the course does not ship
an expected QoR table.

| Lesson | Focus | Main artifacts |
|---|---|---|
| 00 | flow map and toolchain | RTL, logs, first ODB |
| 01 | clocks and I/O constraints | SDC and reports |
| 02 | synthesis | mapped Verilog and statistics |
| 03 | floorplan and PDN | die, core, rows, grid |
| 04 | placement | global/detail placement |
| 05 | CTS | clock tree and skew |
| 06 | routing | guides, DRC, wires |
| 07 | finish and signoff | GDS, SPEF, current signoff reports |

## Commands

```bash
./scripts/learn_physical_design.sh --lesson 00-intro
./scripts/learn_physical_design.sh --deep --lesson 03-floorplan
./scripts/learn_physical_design.sh --status
./scripts/test_course.sh
```

The GUI study uses [`reference/gui-atlas.md`](reference/gui-atlas.md). The
artifact identity and comparison rules are in
[`reference/live-analysis.md`](reference/live-analysis.md). Optional power,
package, thermal, and PEX modules are described in
[`reference/extended-flow.md`](reference/extended-flow.md).

## Completion

Complete the LAB and workbook for every stage, inspect the relevant ODB/log,
and attach the current report paths to the final project. A missing optional
engine must be recorded as `GAP`, with the missing input named.

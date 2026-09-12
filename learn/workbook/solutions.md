# Workbook method

These are methods, not preset answers. Run the command, open the current
report, and record the observation.

## A — Constraints

Read `constraint.sdc` line by line. Identify clock, input delay, output delay,
and any exceptions. Change one input at a time and keep a separate run scope.

## B — Synthesis

Read the Yosys statistics and mapped Verilog. Count cells from the current
files. If the result is empty, inspect the log and top name before proceeding.

## C — Floorplan and PDN

Read die/core/rows and the PDN Tcl. Inspect the current floorplan ODB. A
geometry change changes the comparison contract.

## D — Place and CTS

Compare global and detailed placement from the same run. Read overflow,
wirelength, resizer actions, skew, and current timing paths.

## E — Route

Inspect global-route congestion and detailed-route DRC. Use the current DEF,
ODB, and report paths together.

## F — Finish

Confirm GDS, DEF, CDL, Verilog, SPEF, SDC, and `6_report.json` are current.
Run the signoff scripts and retain each status, including gaps.

## G — Comparison

Validate the shared run id and fingerprints before calculating a delta. Missing
or mismatched data is not a zero and cannot produce a product verdict.

## H — Native tool hand-off

Open the phase target from Studio and note the command, variant, input path,
and output path. In OpenROAD, inspect the database and save it from the same
session. Return to Studio, refresh the phase, and verify that the fingerprint
and modification time changed when the database changed. If they did not,
inspect the save path before running another action.

## I — Floorplan observation

Record die bounds, core bounds, row count, utilization, and PDN status from
the current ODB/DEF. Explain which values came from the database and which
came from a JSON report. A screenshot may show geometry, but it cannot prove
timing, IR, DRC, or LVS.

## J — Gaps and reproducibility

For every `GAP`, preserve the missing executable/model/input and the command
that detected it. A local run can still be useful when an external engine is
unavailable, provided the available backend and its scope are clear. Repeat
the action with the same source tree only when you intend a new invocation;
do not mix its artifacts into a different run's report.

## K — Review checklist

- [ ] The UI phase and CLI phase refer to the same variant.
- [ ] The opened ODB/DEF path is visible in the evidence.
- [ ] The report status is read from the JSON, not inferred from color.
- [ ] Units are written beside every numeric observation.
- [ ] Missing external engines remain labelled `GAP`.
- [ ] A comparison includes its scope and compatible fingerprints.
- [ ] The next command is explicit and reproducible.

The final submission should be understandable without opening a terminal
history. Keep the command, variant, artifact path, report path, status, and
observation together for every stage. When the app displays an updated
floorplan after a native save, include the revision shown by the bridge and
the ODB/DEF path that was refreshed.

Use the app's status badge as a navigation aid, then verify the underlying
file and report yourself.

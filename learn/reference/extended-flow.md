# Extended live flow

The optional chain extends RTL-to-GDS with activity, power, package, thermal,
PEX, and external-tool probes. Every stage consumes current artifacts and
records its own state.

## Chain

1. `run_rtl_sim.sh` produces a current VCD when Icarus is installed.
2. `run_activity_power.sh` joins activity with the current mapped design.
3. `run_vectorless.sh` provides a current vectorless estimate.
4. `run_gridcheck.sh` validates the current PDN geometry.
5. `run_dynamic_ir.sh` solves the current mesh.
6. `run_chip_pdn_ir.sh` and `run_system_pdn.sh` analyze their own meshes.
7. `run_pkg_bump.sh` and `run_pkg_rdl.sh` create package sidecars.
8. `run_thermal_signoff.sh` evaluates the current thermal input.
9. `run_spice_engines.sh`, PEX, and external probes record availability.
10. `run_signoff_phase2.sh` summarizes current package and thermal evidence.

## State rules

| State | Meaning |
|---|---|
| `READY` | current input was found and the tool completed |
| `GAP` | optional engine, model, or input is unavailable |
| `FAIL` | current command completed unsuccessfully |
| `REFUSED` | contract or safety rule rejected the command |

The Studio action registry in `studio/src/lib/run.ts` maps each action to a
job and report. The report path is returned to the UI, which refreshes it
after the job changes state. `FreePDK45.lylvs`, KLayout DRC, bump, thermal,
signoff, and the power chain are all current-artifact checks; none consumes an
archived measurement.

For local heavy work use a shared `PD_FLOW_RUN_DIR` and keep the process
timeout at least as long as the solver timeout.

## Tool hand-off

The hand-off has three explicit parts:

1. the Studio action starts or locates the tool using the selected variant;
2. the tool writes an artifact inside that run's result directory;
3. the Studio panel refreshes the artifact fingerprint and renders its status.

The browser surface never treats a button click as proof that a tool ran. A
successful launch without an output is shown as `GAP` or `FAIL`, according to
the tool result. A native OpenROAD window and the browser viewer can therefore
be open together while both point at the same ODB or DEF.

## Local execution checklist

Before a long action, check the tool card, the active variant, and the input
artifact shown in the phase panel. During execution, keep the live console
open; it exposes the job id, command, elapsed time, and log tail. After the
process exits, inspect the JSON report and confirm its `run_id`, input
fingerprints, output path, and comparison scope.

Optional engines are intentionally independent. For example, a missing
ngspice installation does not invalidate the Python or native PDN result; it
creates a clearly labelled external-engine gap. The same rule applies to
Icarus, OpenRCX, KLayout, and foundry-only decks.

## Signoff ordering

Run the phase action first, then run the signoff action that consumes its
current artifact. Timing uses the current SDC and netlist, DRC uses the
current routed layout, LVS uses the current CDL and layout, and power uses the
current mesh. The phase-two package and thermal actions remain on `/pkg` so
their inputs and reports cannot be confused with the core die flow.

When a check cannot run, keep the command and reason in the report. A report
with a real `GAP` is more useful than a green card with an assumed value.

## Action matrix

| Action | Current input | Current output |
|---|---|---|
| `rtl_sim` | FlowLab RTL and testbench | VCD plus simulation log |
| `gridcheck` | Floorplan PDN ODB | connectivity log and stamp |
| `activity_power` | VCD/SAIF and mapped ODB | activity/power JSON |
| `dynamic_ir` | extracted mesh and current events | solver report and heatmap |
| `chip_pdn_ir` | current chip SPICE mesh | chip-rail report |
| `system_pdn` | package/system ladder | package transient report |
| `thermal_signoff` | current power and thermal deck | thermal status |
| `signoff_phase2` | package and thermal reports | phase-two summary |

Each row is independently inspectable from the Studio action console. The
action name, variant, and report path are part of the evidence, which makes a
long local run easy to resume or audit.

The same contract is used by the command line wrappers and the app API. A
wrapper may stop at the first unavailable prerequisite, while the UI keeps the
reason beside the action. This lets a user fix one dependency and rerun only
the affected action, without rebuilding unrelated stages.

For layout actions, the ODB revision is the synchronization key. If the native
tool saves a new database, the app invalidates the preview cache and reloads
the current image and metadata. Static gallery shots are never used to mask a
missing or changed live artifact.

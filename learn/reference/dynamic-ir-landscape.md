# Dynamic IR / PDN landscape

PDflow is a live-analysis stack: OpenROAD supplies the physical extraction,
the current activity model creates demand, and the numerical solvers evaluate
that demand on the current mesh. Every result carries its input paths,
fingerprints, run identifier, and comparison scope.

## Current architecture

| Layer | Current implementation | Contract |
|---|---|---|
| Physical frontend | OpenROAD ODB, LEF, `write_pg_spice`, optional SPEF | Read geometry and parasitics from the selected invocation |
| Demand | STA arrivals, CCS/ECSM tables when available, VCD/SAIF joins when valid | Missing joins remain `GAP` or `PARTIAL` |
| Solver A | Direct backward-Euler sparse solve | Numerical reference for the same matrix and timestep |
| Solver B | SA-AMG / CG | Compare residuals only against Solver A from the same matrix |
| Solver C | Descriptor RLC rational Krylov | Keeps the inductor state when the active model includes it |
| Solver D | RAS Schwarz | Domain decomposition of the same live operator |
| Analysis | voltage map, timing overlay, EM, thermal, JSON/CSV/SVG | Report-derived values only |

The solvers are complementary views of one current physical problem. A solver
residual is meaningful only when matrix, activity, geometry, constraints, and
run scope all match. Cross-mesh values are shown as separate observations and
are not arithmetically combined.

## Tool boundaries

| Tool | Role in PDflow | Status |
|---|---|---|
| OpenROAD PSM / PDNSim | static on-die power-grid analysis and extraction | integrated |
| `pdn_dynamic.py` | current-demand transient solve and overlays | integrated |
| `vyges-em-ir` | independent bootstrap mesh check | integrated, separate mesh |
| ngspice | optional small-circuit or explicit same-run reference | `GAP` when unavailable |
| Xyce | optional larger transient backend | `GAP` when unavailable |
| OpenSTA | timing and arrival evidence | integrated |
| OpenRCX | finish parasitic extraction | optional; status is reported |
| KLayout / Magic / Netgen | layout inspection and physical checks | integrated or partial per report |

Commercial tools and academic frameworks remain integration references, not
sources of copied metrics. The app reports their absence or partial coverage
explicitly rather than filling a field from another invocation.

## Solver formulation

For a current mesh, the transient system is assembled as a backward-Euler
operator. When package or on-die inductance is enabled, the descriptor state
includes branch currents and the reduced model uses the same state definition.
DirectLU establishes the numerical reference for that solve group; AMG, RAS,
Krylov, and MOR expose residuals and runtime trade-offs against it.

The current report may also include a small external-engine check. Such a
check is labelled by its circuit and scope; it is never promoted to a
full-chip result and never used to replace a missing live artifact.

## Activity and fidelity

The engine distinguishes measured STA/VCD/SAIF joins, table-driven CCS/ECSM
current, and synthetic screening. These labels are part of the report and
flow into the UI. A triangle current model is not presented as a pin-accurate
waveform, and a missing gate-level name join remains a stated gap.

## Review checklist

1. Confirm `ok`, `run_id`, and `comparison_scope` in each report.
2. Confirm the referenced ODB, SPEF, SPICE, activity, and map files exist.
3. Compare solver residuals only within the same live extract.
4. Keep Dynamic IR, chip PDN, package/system PDN, EM, and thermal meshes as
   distinct artifacts unless a report explicitly joins them.
5. Treat unavailable engines as `GAP`; do not infer their output.

The executable source of truth is `learn/scripts/pdn_dynamic.py` and the
current report at `learn/sim/reports/dynamic_ir_<variant>_direct.json`.

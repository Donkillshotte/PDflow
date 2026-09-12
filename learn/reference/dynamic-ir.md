# Dynamic IR

The live chain is:

`ODB/DEF → write_pg_spice → activity → current mesh → transient solver → report`.

Solver A is direct backward-Euler/linear solve. Solver B is an iterative
preconditioned solve. Solver C covers model reduction where the descriptor
inputs are available. Solver D is domain decomposition. They are comparison
engines, not sources of preset values.

Every report must include `run_id`, `comparison_scope`, mesh fingerprint,
activity scenario, timestep, solver/backend, and source artifact paths. The
current heatmap reads the same report and never loads a second mesh to fill a
missing cell.

Optional VCD, SAIF, ngspice, Xyce, thermal, and package paths are explicit
capabilities. If their inputs or binaries are absent, the result is `GAP`.

```bash
export ALLOW_HEAVY_ANALYSIS=1
export PDN_SOLVE_TIMEOUT_S=600
SKIP_NGSPICE=1 learn/scripts/run_dynamic_ir.sh
```

Skipping an unavailable optional engine preserves the rest of the live run;
it does not fabricate an electrothermal or SPICE result.

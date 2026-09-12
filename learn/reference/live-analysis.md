# Live analysis contract

PDflow measures the selected design from the current invocation. Reports are
not compared with archived campaign output and no fixed metric is used as a
pass/fail oracle.

## Scope rules

- Every report records the input design, variant, extract, and run identifier.
- Solver deltas are valid only when both results share the same live mesh and
  invocation scope.
- Missing evidence is reported as `GAP` or `unavailable`; it is never filled
  from another invocation.
- A design comparison is emitted only when the current controller provides
  both sides explicitly. The UI does not invent a base or a second invocation.
- Signoff gates read the current report files for the selected variant.

## Main current-run artifacts

- `learn/sim/reports/dynamic_ir_<variant>_direct.json`
- `learn/sim/reports/sta_ir_aware_<variant>.json`
- `learn/sim/reports/power_signoff_<variant>.json`
- `learn/sim/dse/live_run_<variant>.json`
- `learn/sim/dse/live/<variant>/<run-id>/memory.jsonl`

The Dynamic IR report contains the direct solution, same-mesh solver checks,
activity joins, thermal evidence, and its `comparison_scope`. The STA IR-aware
report consumes the map produced by that same current analysis. DSE receives a
fresh isolated memory path for every invocation.

## Review checklist

1. Confirm `ok`, `run_id`, and `comparison_scope` in the report.
2. Confirm the referenced ODB, SPEF, SPICE, activity, and map files exist.
3. Compare solver residuals only within the same invocation.
4. Treat cross-design or cross-extract values as separate observations unless
   the report explicitly declares a valid same-run comparison.

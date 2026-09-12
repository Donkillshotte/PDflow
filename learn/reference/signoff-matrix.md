# Live signoff matrix

Signoff evaluates the artifacts emitted by the selected invocation.

| Pillar | Current evidence | Missing input means |
|---|---|---|
| Timing | post-SPEF STA JSON and optional IR-aware overlay | `GAP` or incomplete |
| Geometry | route DRC and GDS DRC | `GAP` or fail |
| Equivalence | LVS against the current GDS/CDL | `GAP` or fail |
| Power | activity, mesh, solver and scope | `GAP` or incomplete |
| Package | bump/RDL/system PDN artifacts | `GAP` or incomplete |
| Thermal | current power and thermal model | `GAP` or proxy |

Reports live under `learn/sim/reports/` for the selected variant and include
the input paths. The Studio matrix reads the same files as the CLI scripts.
It does not compare against a fixed table. Timing, geometry, and power must
also retain their own provenance; a report from another mesh or another
constraint contract is not comparable.

```bash
FLOW_VARIANT=flowlab learn/scripts/run_sta_signoff.sh
FLOW_VARIANT=flowlab learn/scripts/run_signoff_all.sh
```

The matrix can display open leftovers and optional gaps. Those states are
valuable diagnostics and are not hidden by a nominally successful command.

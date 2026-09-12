# SPICE and power chain

The power path follows the physical design actually selected by the user:

`RTL → mapped cells → placement → routed ODB → write_pg_spice → activity →
mesh solve → current report → signoff UI`.

`run_rtl_sim.sh` supplies a VCD when available. Activity can also be STA,
SAIF, or an explicitly declared vectorless scenario. `write_pg_spice` records
instance/pin identity; the solver records the mesh and scenario fingerprints.

The UI reads the current report and shows static IR, dynamic IR, solver,
activity, and missing optional engines as separate fields. A chip mesh, system
mesh, and on-die mesh are not merged unless their contracts explicitly match.

Useful commands:

```bash
learn/scripts/run_activity_power.sh
learn/scripts/run_vectorless.sh
learn/scripts/run_dynamic_ir.sh
learn/scripts/run_power_chain.sh
```

When an engine cannot run, preserve the `GAP` and the reason in the report.

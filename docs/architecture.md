# Architecture

The repository keeps sources, tools, live artifacts, and UI adapters separate.

```text
RTL + constraints → OpenROAD/ORFS → current ODB/DEF/GDS/SPEF
                              ├→ current signoff reports
                              └→ current PDN/SPICE solve
                                      ↓
                                Studio jobs/API
```

- `learn/designs` contains tutorial sources and constraints.
- `learn/scripts` contains executable runners and validators.
- `learn/dse` contains product and lab analysis code.
- `learn/sim/dse/live` contains transient run data.
- `learn/sim/reports` contains reports for the selected current variant.
- `studio/src/lib` maps jobs, reports, and artifact viewers into the UI.

The live contract requires a run id and compatible fingerprints before a
comparison. The UI shows report state and source path; it never turns a
missing artifact into a value from another invocation.

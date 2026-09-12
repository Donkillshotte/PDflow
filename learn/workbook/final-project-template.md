# Final project — current RTL to GDS

## 1. Invocation

Use the [live-analysis contract](../reference/live-analysis.md) for every
entry in this workbook. It defines the run id, artifact fingerprints, and
the rules for declaring a measurement unavailable.

- Design and top:
- Variant:
- Run id:
- Command:
- Source RTL and constraint paths:

## 2. Stage evidence

| Stage | Input | Output | Status | Key observation |
|---|---|---|---|---|
| synth | | | | |
| floorplan | | | | |
| place | | | | |
| cts | | | | |
| route | | | | |
| finish | | | | |

## 3. Current metrics

Copy area, cells, WNS, TNS, power, leakage, IR, DRC, and LVS from the
reports produced by this invocation. Include units and source paths.

## 4. Comparison

If you ran a challenger, record the shared `run_id`, constraint contract,
netlist/RTL fingerprint, geometry fingerprint, mesh fingerprint, and
`comparison_scope`. If any differ, mark the comparison unavailable.

## 5. GUI evidence

Attach or describe one current ODB view using
[`gui-atlas.md`](../reference/gui-atlas.md). Name the ODB path, layer filters,
and the matching log/report.

## 6. Signoff and gaps

- [ ] STA report inspected
- [ ] DRC report inspected
- [ ] LVS report inspected
- [ ] Power/IR report inspected
- [ ] Optional gaps recorded explicitly
- [ ] No report was copied from another invocation

## 7. Reflection

Explain one timing issue, one physical issue, one power issue, and one next
experiment. Include the exact command you would run next.

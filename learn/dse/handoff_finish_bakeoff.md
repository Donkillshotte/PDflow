# Bake-off: DSE winners through the same `make finish`

Executed the plan in `handoff_finish_plan.md`. Same oven as finish
`flowlab` (SDC 0.46 ns, `CORE_UTILIZATION=35`, tutorial config). Only the
gate-level netlist changes. Yosys skipped (`SYNTH_NETLIST_FILES`).
Isolated variants: `flowlab_dse_small`, `flowlab_dse_fast`. The
`flowlab/` tree was not touched (6_report / 6_final.odb sha identical to freeze).

## Verdict in three lines

1. **A stays the dish.** Finish WNS −37 ps vs B −338 ps and C −187 ps.
2. **B is smaller** (610 vs 940 µm²) but not on time — not a product win.
3. **C**, the “fast” recipe on paper, finishes slower with **more**
   repair buffers (198 vs 132). Area 963 µm², not smaller.

Tie/regression on product. DSE search remains useful as a
lab; on GCD it **does not** beat the ORFS recipe once cooked end-to-end.

## Table (same `6_report.json`)

| Axis | A flowlab | B small (`sub_twos_complement`) | C fast (`abc_speed`) |
|---|---|---|---|
| WNS setup | **−37.2 ps** | −338 ps | −187 ps |
| TNS setup | **−0.595 ns** | −13.09 ns | −5.98 ns |
| Stdcell | 940 µm² / 680 | **610 µm² / 439** | 963 µm² / 660 |
| Repair buf | **132** | 126 | 198 |
| Clk buf | 7 | 7 | 7 |
| Power | 3.93 mW | 2.43 mW | 5.53 mW |
| Util finish | 54.9% | 53.7% | 56.8% |
| Die | 1970 µm² | 1305 µm² | 1941 µm² |
| Place WNS | **+12 ps** | −314 ps | −117 ps |
| PSM VDD drop | 6.67 mV | 3.33 mV | 8.26 mV |

Place already tells the result: A was meeting after DP. B and C arrive at
placement already late; end-of-flow buffers do not recover to A.

PSM IR **is not** the DirectLU comparison. Different dies → different meshes. Phase 2
DirectLU skipped (non-blocking). Gold 45.298 unrestamped.

A's 55% is util **after** repairs, not the knob. The common knob is 35%.

## What did not happen

- No `make finish` from the DSE controller.
- No AES / Krylov.
- No cone ABC stitching.
- Crashes: none. Both cooks `errors=0`.

## After

Stitching cone ABC or putting handoff in the DSE loop **is not** justified
by this GCD. If repeated, the candidate to cook is one that at *place*
is already meeting, not only smaller on paper.

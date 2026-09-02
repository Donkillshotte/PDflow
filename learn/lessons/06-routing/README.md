# Lesson 06 — Routing

Routing is the step from “cells with pins” to “wires the fab can print”.

On the GCD `learn` the timing **worsens** when wires become real:

| Stage | worst slack max | setup viol | Comment |
|---|---|---|---|
| Detailed place | **+0.01 ns** | 0 | placement estimate, optimistic |
| CTS final | **−0.04 ns** | 32 | propagated clock |
| Global route | **−0.05 ns** | 43 | RC from **guide** |
| Finish SPEF | **−0.04 ns** | 38 | extraction; TNS −0.60 |

Do not “adjust numbers by hand”: understand **why** the sign changes. GRT sees congestion and corridor length; SPEF sees geometric RC.

## Objectives

- Distinguish GRT guides from DRT wires (same net, two ODBs)
- Read congestion heatmap (`orfs_final_congestion.png`)
- Understand why DRT **aborts** without `grt::have_routes`
- Antenna at conceptual level + loop in `detail_route.tcl`

## Reading

- This README
- `walkthrough-route.tcl.md`
- LAB 06
- Atlas §2, §5.8–5.9, §9

## Two different problems

**Global routing:** assign bands (2D / gcell resources) minimizing overflow. Output: `route.guide` (thousands of lines on GCD).

**Detailed routing:** mask geometry: width, spacing, via, enclosure. Output: metal in ODB + `5_route_drc.rpt` (0 lines = clean on our GCD).

DRT without guides is paving without a route: `detail_route.tcl` lines 5–8 exits with error and sends you to `make gui_grt`.

## Sub-stages ORFS

| Step | Output | What happens to timing |
|---|---|---|
| 5_1_grt | GRT + `estimate_parasitics -global_routing` + incremental repair | more honest slack than place |
| 5_2_route | TritonRoute + `repair_antennas` possible re-route | geometry; STA still without SPEF |
| 5_3_fillcell | fill post-route | process density |

GRT **still repairs timing** because guides are a better RC model than placement. Then incremental DPL + `global_route -start_incremental` / `-end_incremental` re-routes only touched nets.

## Layer Nangate45 in *this* GUI

| Layer | Qt 26Q2 color | Typical GCD role |
|---|---|---|
| metal1 | blue | rails + local pins |
| metal2 | red | signal |
| metal3 | green | signal, opposite direction |
| metal4/7 | yellow / pink | PDN strap |

Exercise: M2 only, then M3 only (`gui-atlas` Tcl). Dominant direction should change.

## Congestion

Heatmap `orfs_final_congestion.png`: gcell grid, green = free, red = full. On the GCD the center is hot, the edges cold: consistent with placement blob.

If GRT does not converge: `5_1_grt-failed.odb` + congestion report. Fix: less density, more util headroom, fewer buffers (SDC).

## Antenna

During etch, a long wire on a gate is a capacitor that charges. `repair_antennas` inserts diodes; then **re-runs** `detailed_route`. Log: `drt_antennas.log`. You do not need plasma physics: you need to know that ORFS can **iterate**.

`DETAILED_ROUTE_END_ITERATION` / `DETAILED_ROUTE_ARGS -droute_end_iter 5`: stops TritonRoute early for debug (comment in `detail_route.tcl` lines 30–42).

## Files

| Files | If empty / non-empty |
|---|---|
| `route.guide` | must be large |
| `5_route_drc.rpt` | empty = DRC clean (GCD) — see also unified [`drc_signoff`](../../reference/signoff-matrix.md) post-finish |
| `5_global_route.rpt` | overflow + GRT slack |
| `maze.log` | DRT debug |

## GUI

1. `gui_5_1_grt.odb` — `win_grt.png`, `07_grt.png`
2. `gui_5_2_route.odb` — `08_route_labeled.png`, isolate M2/M3

## Power & SPICE chain

Routing completes geometry for IR/SPEF. PDNSim uses the **post-route/finish** design. See [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-06-routing).

| Link | Where |
|---|---|
| FlowLab | [route](/flow?phase=route) |

## Duration

README+walkthrough 50–70 min, LAB 90–120 min, **total ~3 hours**.

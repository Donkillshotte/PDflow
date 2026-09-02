# Lesson 06 — Routing

Routing is il step from “celle con pin” a “wires the fab can print”.

On the GCD `learn` the timing **worsens** when wires become real:

| Stadio | worst slack max | setup viol | Commento |
|---|---|---|---|
| Detailed place | **+0.01 ns** | 0 | placement estimate, optimistic |
| CTS final | **−0.04 ns** | 32 | propagated clock |
| Global route | **−0.05 ns** | 43 | RC from **guide** |
| Finish SPEF | **−0.04 ns** | 38 | extraction; TNS −0.60 |

Non “adjust numbers by hand”: understand **why** the sign changes. GRT sees congestion e corridor length; SPEF vede RC geometric.

## Objectives

- Distinguere guide GRT da wire DRT (stessa net, due ODB)
- Leggere congestion heatmap (`orfs_final_congestion.png`)
- Capire because DRT **aborts** without `grt::have_routes`
- Antenna at conceptual level + loop in `detail_route.tcl`

## Reading

- This README
- `walkthrough-route.tcl.md`
- LAB 06
- Atlas §2, §5.8–5.9, §9

## Two different problems

**Global routing:** assign bands (2D / gcell resources) minimizzando overflow. Output: `route.guide` (thousands of lines on GCD).

**Detailed routing:** mask geometry: width, spacing, via, enclosure. Output: metal in ODB + `5_route_drc.rpt` (0 righe = clean sul nostro GCD).

DRT senza guide is pave without a route: `detail_route.tcl` riga 5–8 exits with error and sends you a `make gui_grt`.

## Sub-stages ORFS

| Step | Output | Cosa succede al timing |
|---|---|---|
| 5_1_grt | GRT + `estimate_parasitics -global_routing` + repair incremental | more honest slack than place |
| 5_2_route | TritonRoute + `repair_antennas` eventuale re-route | geometria; STA ancora senza SPEF |
| 5_3_fillcell | fill post-route | density processo |

GRT **still repairs timing** because le guide are un modello RC migliore del placement. Poi DPL incremental + `global_route -start_incremental` / `-end_incremental` re-routes only touched nets.

## Layer Nangate45 in *questa* GUI

| Layer | Qt 26Q2 color | Typical GCD role |
|---|---|---|
| metal1 | blu | rails + local pins |
| metal2 | rosso | segnale |
| metal3 | green | segnale, opposite direction |
| metal4/7 | giallo / rosa | PDN strap |

Exercise: solo M2, poi solo M3 (`gui-atlas` Tcl). Dominant direction should change.

## Congestion

Heatmap `orfs_final_congestion.png`: gcell grid, green = aria, red = full. On the GCD il centro is caldo, i edges cold: consistent with placement blob.

Se GRT does not converge: `5_1_grt-failed.odb` + congestion report. Fix: less density, more util headroom, fewer buffers (SDC).

## Antenna

During etch, un long wire on a gate is un capacitor that charges. `repair_antennas` inserts diodes; poi **re-runs** `detailed_route`. Log: `drt_antennas.log`. You do not need la plasma physics: you need sapere che ORFS can **iterate**.

`DETAILED_ROUTE_END_ITERATION` / `DETAILED_ROUTE_ARGS -droute_end_iter 5`: stops TritonRoute early for debug (comment in `detail_route.tcl` righe 30–42).

## Files

| Files | If empty / non vuoto |
|---|---|
| `route.guide` | must be large |
| `5_route_drc.rpt` | vuoto = DRC clean (GCD) — see anche [`drc_signoff`](../../reference/signoff-matrix.md) unificato post-finish |
| `5_global_route.rpt` | overflow + slack GRT |
| `maze.log` | debug DRT |

## GUI

1. `gui_5_1_grt.odb` — `win_grt.png`, `07_grt.png`
2. `gui_5_2_route.odb` — `08_route_labeled.png`, isola M2/M3

## Power & SPICE chain

Il routing completes geometry per IR/SPEF. PDNSim use il design **post-route/finish**. See [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-06-routing).

| Link | Where |
|---|---|
| FlowLab | [route](/flusso?phase=route) |

## Duration

README+walkthrough 50–70 min, LAB 90–120 min, **total ~3 hours**.

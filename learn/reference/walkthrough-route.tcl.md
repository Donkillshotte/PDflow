# Annotated walkthrough — global_route.tcl e detail_route.tcl

Two scripts, two abstractions. Files: `flow/scripts/global_route.tcl`, `detail_route.tcl` (ORFS 26Q2).

Numeri `learn`: GRT worst slack **−0.05 ns** / 43 viol; DRC report typically **empty**; finish SPEF −0.04 / 38 viol.

---

## Global route — input

`4_cts.odb` + `4_cts.sdc`. Cells + clock tree already there. Without legal CTS, GRT starts on a mess.

`pin_access` (line ~26): opens access paths to pins. Without pin access the router cannot enter the cell.

---

## `global_route`

```tcl
log_cmd global_route -congestion_report_file ... {*}$GLOBAL_ROUTE_ARGS
```

Produces **guides**, not mask wire. Failure: `5_1_grt-failed.odb` + congestion report. GUI: `gui_grt` come dice l’errore di `detail_route.tcl`.

Heatmap: `gui-shots/orfs_final_congestion.png` (gcell green/red).

---

## Incremental repair (the piece nobody skips reading)

After GRT:

1. `set_propagated_clock` + `estimate_parasitics -global_routing`
2. `repair_design_helper` / `repair_timing_helper` — more buffers, with RC **from guides**
3. `global_route -start_incremental` → `detailed_placement` → `-end_incremental`  
   Re-routes **only** nets touched by repair

Teaching note: GRT is not one-shot. It is a loop with RSZ. For this the log is long e l’area sale ancora (remember CTS 48% → finish still has fill).

Output: `5_1_grt.odb`, `route.guide`.

```bash
head -20 results/nangate45/gcd/learn/route.guide
wc -l results/nangate45/gcd/learn/route.guide
```

Each block is net + layer + bbox. This is not a PATH GDS.

---

## Detailed route — guardie

```tcl
if { ![grt::have_routes] } {
  error "Global routing failed, run `make gui_grt` ..."
}
if { $::env(SKIP_DETAILED_ROUTE) } { write odb; exit }
```

Poi `set_propagated_clock`, argomenti TritonRoute (`VIA_IN_PIN_*`, `OR_SEED`, `DETAILED_ROUTE_END_ITERATION`).

Policy default (comment lines 30–42): if you do not set `DETAILED_ROUTE_ARGS`, use `-drc_report_iter_step 5` so it does not flood you with huge DRC at iter 1–2.

```tcl
detailed_route -output_drc reports/5_route_drc.rpt \
  -output_maze results/maze.log ...
```

---

## Antenna loop

```tcl
if { [repair_antennas] } { detailed_route ... }
while { [check_antennas] && iters < MAX } {
  repair_antennas
  detailed_route ...
}
```

Poi `check_antennas -report_file drt_antennas.log`.  
`design_is_routed` false → error “unrouted nets”.

**No** `report_metrics` here: trailing comment says extraction is at finish. GRT slack in report `5_global_route.rpt` is still from **guides**, not SPEF.

---

## GUI comparison

| ODB | PNG | Cosa is |
|---|---|---|
| `5_1_grt` | `win_grt.png`, `07_grt.png` | corridors |
| `5_2_route` | `08_route_labeled.png` | M2 red / M3 green spaghetti |

```tcl
gui::set_display_controls "Layers/*" visible false
gui::set_display_controls "Layers/metal2" visible true
gui::fit
```

---

## Checkpoint

1. Why DRT richiede GRT?
2. `5_route_drc.rpt` vuoto = ?
3. Why `estimate_parasitics -global_routing` > `-placement`?
4. What it does `-droute_end_iter 5`?

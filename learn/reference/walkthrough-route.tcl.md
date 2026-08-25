# Walkthrough annotato — global_route.tcl e detail_route.tcl

Due script, due astrazioni. File: `flow/scripts/global_route.tcl`, `detail_route.tcl` (ORFS 26Q2).

Numeri `learn`: GRT worst slack **−0.05 ns** / 43 viol; DRC report tipicamente **vuoto**; finish SPEF −0.04 / 38 viol.

---

## Global route — input

`4_cts.odb` + `4_cts.sdc`. Celle + albero clock già lì. Senza CTS legale, GRT parte su un pasticcio.

`pin_access` (riga ~26): apre vie d’ingresso ai pin. Senza pin access il router “non entra” nella cella.

---

## `global_route`

```tcl
log_cmd global_route -congestion_report_file ... {*}$GLOBAL_ROUTE_ARGS
```

Produce **guide**, non wire mask. Fallimento: `5_1_grt-failed.odb` + congestion report. GUI: `gui_grt` come dice l’errore di `detail_route.tcl`.

Heatmap: `gui-shots/orfs_final_congestion.png` (gcell verde/rosso).

---

## Incremental repair (il pezzo che nessuno salta a leggere)

Dopo GRT:

1. `set_propagated_clock` + `estimate_parasitics -global_routing`
2. `repair_design_helper` / `repair_timing_helper` — ancora buffer, con RC **da guide**
3. `global_route -start_incremental` → `detailed_placement` → `-end_incremental`  
   Ri-routa **solo** le net toccate dal repair

Didattica: GRT non è one-shot. È un loop con RSZ. Per questo il log è lungo e l’area sale ancora (ricorda CTS 48% → finish ancora fill).

Output: `5_1_grt.odb`, `route.guide`.

```bash
head -20 results/nangate45/gcd/learn/route.guide
wc -l results/nangate45/gcd/learn/route.guide
```

Ogni blocco è net + layer + bbox. Non è un PATH GDS.

---

## Detailed route — guardie

```tcl
if { ![grt::have_routes] } {
  error "Global routing failed, run `make gui_grt` ..."
}
if { $::env(SKIP_DETAILED_ROUTE) } { write odb; exit }
```

Poi `set_propagated_clock`, argomenti TritonRoute (`VIA_IN_PIN_*`, `OR_SEED`, `DETAILED_ROUTE_END_ITERATION`).

Policy default (commento righe 30–42): se non setti `DETAILED_ROUTE_ARGS`, usa `-drc_report_iter_step 5` così non ti bombarda di DRC enormi alle iter 1–2.

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

**Non** c’è `report_metrics` qui: il commento in coda dice che l’estrazione è al finish. Slack GRT nel report `5_global_route.rpt` è ancora da **guide**, non SPEF.

---

## GUI confronto

| ODB | PNG | Cosa è |
|---|---|---|
| `5_1_grt` | `win_grt.png`, `07_grt.png` | corridoi |
| `5_2_route` | `08_route_labeled.png` | spaghetti M2 rosso / M3 verde |

```tcl
gui::set_display_controls "Layers/*" visible false
gui::set_display_controls "Layers/metal2" visible true
gui::fit
```

---

## Checkpoint

1. Perché DRT richiede GRT?
2. `5_route_drc.rpt` vuoto = ?
3. Perché `estimate_parasitics -global_routing` > `-placement`?
4. Cosa fa `-droute_end_iter 5`?

# Walkthrough annotato — global_route.tcl e detail_route.tcl

Due script, due livelli di astrazione.

---

## Global route (`flow/scripts/global_route.tcl`)

### Input
`4_cts.odb` + `4_cts.sdc` — celle già piazzate, clock tree esistente.

### pin_access (riga 26)

Apre "vie" di accesso ai pin delle celle: il router deve poter entrare nei pin senza violare spacing.

### global_route (righe 14–19)

```tcl
log_cmd global_route -congestion_report_file ... {*}$GLOBAL_ROUTE_ARGS
```

**Cosa produce:**
- Assegnazione di **guide** per ogni net (fasce 2D sui layer)
- **Non** produce geometria mask-ready
- Report congestione se overflow

**Fallimento:** se GRT non converge, scrive `5_1_grt-failed.odb`.  
Apri `gui_5_1_grt-failed.odb` + congestion report in DRC viewer.

### Incremental repair (righe 51–74)

Dopo GRT:
1. `estimate_parasitics -global_routing` — RC da guide (più realistico di placement)
2. `repair_design` / `repair_timing` — buffer ancora, con delay più credibili
3. `global_route -start_incremental` + `detailed_placement` + `-end_incremental`  
   Ri-routa solo net toccate dal repair

**Didattica:** il routing globale è *iterativo* con il timing, non un one-shot.

### Output
`5_1_grt.odb` + `route.guide`

**GUI:** `gui_5_1_grt.odb` — overlay guide, heatmap congestion.

---

## Detailed route (`flow/scripts/detail_route.tcl`)

### Guardia (righe 5–8)

```tcl
if { ![grt::have_routes] } {
  error "Global routing failed..."
}
```

Senza guide valide, DRT non parte.

### detailed_route (righe 49–54)

```tcl
detailed_route -output_drc $::env(REPORTS_DIR)/5_route_drc.rpt \
  -output_maze $::env(RESULTS_DIR)/maze.log ...
```

TritonRoute:
- assegna layer/via reali
- rispetta width, spacing, enclosure
- itera finché DRC → 0 o max iterazioni

`DETAILED_ROUTE_END_ITERATION` — per debug, ferma dopo N iter (vedi commento righe 30–38).

### Antenna repair (righe 56–71)

Carica su gate durante fabbricazione (plasma etch).  
`repair_antennas` inserisce diodi; poi **ri-routa**.

### Guardia finale (77–79)

```tcl
if { ![design_is_routed] } {
  error "Design has unrouted nets."
}
```

---

## Come studiare i due ODB

| Snapshot | Cosa vedi | Cosa NON vedi |
|---|---|---|
| `5_1_grt.odb` | guide, congestion | wire finali |
| `5_2_route.odb` | metal1–metal10, via | — |

Esercizio: stessa net, confronta guida GRT vs geometria DRT.

---

## Checkpoint

1. Perché DRT richiede GRT?
2. Cosa contiene `5_route_drc.rpt` quando è vuoto?
3. Perché `estimate_parasitics -global_routing` è più accurato di `-placement`?

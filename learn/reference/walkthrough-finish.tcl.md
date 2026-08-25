# Walkthrough annotato — finish (fill, report, GDS)

Fase 6 ORFS: da layout routato a **deliverable fab**.

Script: `density_fill.tcl`, `final_report.tcl` / `final_outputs.tcl`, merge KLayout.

---

## 6_1 fill (`density_fill.tcl`)

```tcl
load_design 5_route.odb 5_route.sdc
if { $::env(USE_FILL) } {
  density_fill -rules $::env(FILL_CONFIG)
}
```

**Fill cells:** dummy metal/celle per densità di processo (CMP, etching uniforme).  
Su Nangate45 spesso `USE_FILL` è on: vedrai centinaia di `FILLCELL*` in `report_cell_usage`.

**Didattica:** fill **non** cambia funzione logica; cambia area/density e a volte parassiti.

Output: `6_1_fill.odb`

---

## 6_report (`final_report.tcl` + `final_outputs.tcl`)

Sequenza:

1. `write_def` / `write_verilog` → `6_final.def`, `6_final.v`
2. Se `RCX_RULES` esiste: **OpenRCX** `extract_parasitics` → `6_final.spef`
3. `read_spef` + STA
4. IR drop (`analyze_power_grid`) se voltaggi definiti
5. `report_metrics 6 "finish"` → `6_finish.rpt`
6. Screenshot GUI (`save_images.tcl`) — può fallire headless; **non** invalida il GDS

**Mismatch versioni:** ORFS master + OpenROAD 26Q2 può crashare su `get_property default` in save_images. Il corso pinna ORFS 26Q2 per questo.

---

## Merge GDS (KLayout)

Makefile: `klayout.sh` + `util/def2stream.py`

```
6_final.def + NangateOpenCellLibrary.gds  →  6_1_merged.gds  →  6_final.gds
```

KLayout stream-out: mappa celle LEF a geometrie GDS della libreria.

**Warning tipico:** DEF UNITS vs DBU reader — informativo se il merge completa.

---

## Pacchetto signoff (cosa consegneresti)

| File | Destinatario |
|---|---|
| `6_final.gds` | mask shop / foundry |
| `6_final.def` | backend / ECO |
| `6_final.spef` | STA signoff |
| `6_final.sdc` | STA signoff |
| `6_final.v` | LVS / sim post-layout |

---

## Timing: tre stime a confronto

| Fase | Stima delay | Accuratezza |
|---|---|---|
| Synth | liberty only | bassa |
| Place | `estimate_parasitics -placement` | media |
| GRT | `estimate_parasitics -global_routing` | buona |
| Finish | SPEF OpenRCX | migliore disponibile open-source |

**Esercizio:** tabella WNS alle quattro stime sullo stesso SDC.

---

## Checkpoint

1. Fill cambia la logica? 
2. SPEF senza routing dettagliato ha senso?
3. Perché KLayout e non OpenROAD per il GDS merge?

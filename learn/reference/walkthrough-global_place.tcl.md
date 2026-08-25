# Walkthrough annotato — global_place.tcl e detail_place.tcl

File: `flow/scripts/global_place.tcl` e `flow/scripts/detail_place.tcl`  
ODB: `3_2_place_iop.odb` → `3_3_place_gp.odb` → (resizer) `3_4` → `3_5_place_dp.odb`

Leggi questo testo **con lo script aperto a fianco**. I numeri di riga sono quelli di ORFS **26Q2**.

---

## Perché due script

**Global placement (GP)** sparge le celle nel core minimizzando wirelength (+ densità, opzionale timing). Le celle possono **sovrapporsi** nel disegno: non sono ancora sui site.

**Detailed placement (DP)** legalizza: ogni istanza su un site di una row, overlap zero, mirroring, eventuale `improve_placement`.

In mezzo ORFS lancia il **resizer** (`3_4_place_resized.odb`): buffer/upsize. Quei buffer nuovi *devono* passare da DP. Per questo l’ordine è GP → RSZ → DP, non DP prematuro.

GUI: [gui-atlas.md](./gui-atlas.md) §5.5–5.6 (`win_place_gp.png` vs `win_place_dp.png`).

---

## global_place.tcl — blocco load (righe 1–5)

```tcl
utl::set_metrics_stage "globalplace__{}"
source $::env(SCRIPTS_DIR)/load.tcl
erase_non_stage_variables place
load_design 3_2_place_iop.odb 2_floorplan.sdc
source_step_tcl PRE GLOBAL_PLACE
```

- Input **IOP già fatto**: i pin sul bordo **tirano** le celle. Se confronti `3_1_place_gp_skip_io` e `3_3`, le celle interne si spostano.
- SDC ancora `2_floorplan.sdc`: il clock è lo stesso; i parassiti no.

Hook `PRE GLOBAL_PLACE`: puoi iniettare Tcl (corso: non serve).

---

## dont_use e remove_buffers (righe 7–11)

```tcl
set_dont_use $::env(DONT_USE_CELLS)
if { $::env(GPL_TIMING_DRIVEN) } {
  remove_buffers
}
```

`DONT_USE_CELLS` (platform): celle vietate (es. drive eccessivi, latch).  
Se GP è timing-driven, ORFS **toglie** buffer precedenti per non far ottimizzare un netlist già “inquinato”; GP riparte pulito, RSZ reinserirà.

---

## buffer_ports (righe 17–22)

```tcl
if { ![env_var_exists_and_non_empty FOOTPRINT] } {
  if { !$::env(DONT_BUFFER_PORTS) } {
    buffer_ports {*}[env_var_or_empty BUFFER_PORTS_ARGS]
  }
}
```

Sui chiplet/`FOOTPRINT` non bufferizza i port (altro flusso). Sul GCD: **sì**, buffer sulle porte. Slew/cap dei pin I/O devono essere legali **prima** che GP sposti tutto.

**Esperimento (avanzato):** `DONT_BUFFER_PORTS=1 make place` e guarda slew sui port nel resizer report.

---

## Argomenti di `global_placement` (righe 24–50)

```tcl
append_env_var global_placement_args GPL_ROUTABILITY_DRIVEN -routability_driven 0
if { $::env(GPL_TIMING_DRIVEN) } {
  lappend global_placement_args {-timing_driven}
  ...
}
lappend global_placement_args -force_center_initial_place
lappend global_placement_args -min_phi_coef $::env(MIN_PLACE_STEP_COEF)
lappend global_placement_args -max_phi_coef $::env(MAX_PLACE_STEP_COEF)
```

| Flag | Idea |
|---|---|
| `-routability_driven` | penalizza regioni che GRT odierà |
| `-timing_driven` | usa slack stimato, non solo HPWL |
| `-force_center_initial_place` | parte dal centro die (GCD: blob centrale che vedi in GUI) |
| `phi` min/max | passo del solver; se min>max → **GPL 200** e stop |

---

## do_placement (righe 52–61)

```tcl
proc do_placement { global_placement_args } {
  set all_args [concat [list -density [place_density_with_lb_addon] \
    -pad_left $::env(CELL_PAD_IN_SITES_GLOBAL_PLACEMENT) \
    -pad_right $::env(CELL_PAD_IN_SITES_GLOBAL_PLACEMENT)] \
    $global_placement_args]
  lappend all_args {*}[env_var_or_empty GLOBAL_PLACEMENT_ARGS]
  log_cmd global_placement {*}$all_args
}
```

- **Density** = target di riempimento. Nel corso `PLACE_DENSITY_LB_ADDON=0.20` alza il pavimento: più aria, meno overflow, un po’ più wirelength.
- **Pad** in *sites*: spazio obbligatorio tra celle (routing). Troppo pad → utilizzazione effettiva sale.

Se `global_placement` lancia eccezione: scrive `3_3_place_gp-failed.odb` (righe 63–67). Aprilo in GUI: è il debug.

Poi `estimate_parasitics -placement` e `report_metrics 3 "global place"`.

Output: `3_3_place_gp.odb`.

**Log `3_3_place_gp.log`:** cerca overflow → deve tendere a 0. Se resta alto, density/util/SDC sono sbagliati *prima* del CTS.

---

## detail_place.tcl

```tcl
load_design 3_4_place_resized.odb 2_floorplan.sdc
...
set_placement_padding -global \
  -left $::env(CELL_PAD_IN_SITES_DETAIL_PLACEMENT) \
  -right $::env(CELL_PAD_IN_SITES_DETAIL_PLACEMENT)
detailed_placement {*}[env_var_or_empty DETAIL_PLACEMENT_ARGS]
if { $::env(ENABLE_DPO) } {
  improve_placement ...
}
optimize_mirroring
utl::info FLW 12 "Placement violations [check_placement -verbose]."
```

| Comando | Ruolo |
|---|---|
| `detailed_placement` | legalizza sui site |
| `improve_placement` | DPO: micro-ottimizza wirelength legale |
| `optimize_mirroring` | flip delle celle (N/S) se il LEF lo consente |
| `check_placement -verbose` | overlap, out-of-row, off-site |

Fallimento → `3_5_place_dp-failed.odb`. **Non** è lo stesso errore DPL-0038 del CTS (quello è *dopo* i buffer clock, core già pieno).

Output: `3_5_place_dp.odb` poi ORFS copia/allinea a `3_place.odb`.

---

## Cosa guardare in GUI (pixel)

1. `gui_3_3_place_gp.odb` — celle “a nuvola”, overlap visivo possibile.
2. `gui_3_5_place_dp.odb` — stesse celle sulle righe blu.
3. Inspector su una `AND2_X1`: coordinate cambiano tra GP e DP (spesso di frazioni di µm).

Vedi anche canvas `save_image`: `gui-shots/04_place_gp.png` e `05_place_dp.png`.

---

## Checkpoint

1. Perché `load_design` di GP usa `3_2_place_iop.odb` e non `2_floorplan.odb`?
2. Cosa misura overflow?
3. `improve_placement` può creare overlap? (no: resta nel legale)
4. Relazione `PLACE_DENSITY_LB_ADDON` ↔ DPL-0038 alla lezione 05?

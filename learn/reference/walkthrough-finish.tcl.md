# Walkthrough annotato — finish (`final_report.tcl` 26Q2)

Da layout routato a **deliverable**. Script: `density_fill.tcl`, `final_report.tcl`, merge KLayout.

Numeri `learn`: WNS **−0.04**, TNS **−0.60**, `period_min=0.50` ns (fmax ~2011 MHz), setup skew ~0, IR drop heatmap ~0–5 mV.

---

## 6_1 fill

```tcl
load_design 5_route.odb 5_route.sdc
if { $::env(USE_FILL) } {
  density_fill -rules $::env(FILL_CONFIG)
}
```

Dummy per densità di processo. **Non** cambia la funzione. Find `FILLCELL` in GUI. Output `6_1_fill.odb`.

---

## `final_report.tcl` riga per riga (blocchi)

```tcl
load_design 6_1_fill.odb 6_1_fill.sdc
set_propagated_clock [all_clocks]
global_connect
orfs_write_db .../6_final.odb
```

`global_connect`: le istanze create da RSZ/CTS devono attaccarsi a VDD/VSS. Senza, LVS/IR piangono.

```tcl
deleteRoutingObstructions
write_def  .../6_final.def
write_verilog .../6_final.v -remove_cells [find_physical_only_masters]
```

Il `.v` di signoff **toglie** celle physical-only (fill, tap, …) perché LVS/sim non le vogliono come logica. Per questo `wc -l 6_final.v` ≠ `1_2_yosys.v` ma non “è un altro circuito”.

---

## OpenRCX / SPEF

```tcl
if { RCX_RULES && ! SKIP_DETAILED_ROUTE } {
  define_process_corner -ext_model_index 0 X
  extract_parasitics -ext_model_file $::env(RCX_RULES)
  write_spef .../6_final.spef
  read_spef .../6_final.spef
  # IR drop se PWR_NETS_VOLTAGES / GND_NETS_VOLTAGES
} else {
  estimate_parasitics -global_routing   ;# fallback
}
```

Nangate45 nel corso **ha** RCX: aspetta SPEF. `head` di `6_final.spef`: `*D_NET`.

IR: `analyze_power_grid` → heatmap `orfs_final_ir_drop.png`. Sul GCD pochi mV: la PDN M1–M4–M7 basta. Su un die mm² no.

Poi `report_cell_usage`, `report_metrics 6 "finish"` → `6_finish.rpt`.

```tcl
if { [ord::openroad_gui_compiled] } {
  gui::show "source .../save_images.tcl" false
}
```

Headless può fallire; le immagini in `reports/*.webp.png` se ci sono sono oro didattico (worst path, clocks, congestion). Copiate in `gui-shots/orfs_*.png`.

Crash `STA-2204 get_property default`: ORFS **master** vs OpenROAD 26Q2. Tag pinnato 26Q2.

---

## Merge GDS

```
6_final.def + NangateOpenCellLibrary.gds → 6_1_merged.gds → 6_final.gds
```

KLayout stream-out, non OpenROAD. Warning UNITS/DBU: informativo se il file GDS ha size > 0 (`ls -lh 6_final.gds`).

---

## Come leggere `6_finish.rpt`

| Sezione | Cosa copiare nel progetto |
|---|---|
| `report_wns` / `report_tns` | −0.04 / −0.60 |
| `report_clock_min_period` | 0.50 ns vs SDC 0.46 |
| `report_clock_skew` | source/target latency |
| `setup_violation_count` | 38 |
| worst path | start/end FF |

Overlay path: `orfs_final_worst_path.png` (launch ciano, signal rosso).

---

## Checkpoint

1. Fill cambia la logica?
2. Perché `write_verilog -remove_cells`?
3. SPEF senza DRT ha senso?
4. Perché fmax 2.01 GHz con SDC 0.46 ns (~2.17 GHz)?

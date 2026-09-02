# Annotated walkthrough — finish (`final_report.tcl` 26Q2)

From routed layout to **deliverable**. Script: `density_fill.tcl`, `final_report.tcl`, merge KLayout.

`learn` numbers: WNS **−0.04**, TNS **−0.60**, `period_min=0.50` ns (fmax ~2011 MHz), setup skew ~0, IR drop heatmap ~0–5 mV.

---

## 6_1 fill

```tcl
load_design 5_route.odb 5_route.sdc
if { $::env(USE_FILL) } {
  density_fill -rules $::env(FILL_CONFIG)
}
```

Dummy for process density. **Does not** change function. Find `FILLCELL` in GUI. Output `6_1_fill.odb`.

---

## `final_report.tcl` line by line (blocks)

```tcl
load_design 6_1_fill.odb 6_1_fill.sdc
set_propagated_clock [all_clocks]
global_connect
orfs_write_db .../6_final.odb
```

`global_connect`: instances created by RSZ/CTS must attach to VDD/VSS. Without it, LVS/IR fail.

```tcl
deleteRoutingObstructions
write_def  .../6_final.def
write_verilog .../6_final.v -remove_cells [find_physical_only_masters]
```

Signoff `.v` **removes** physical-only cells (fill, tap, …) because LVS/sim do not want them as logic. For this `wc -l 6_final.v` ≠ `1_2_yosys.v` but not “another circuit”.

---

## OpenRCX / SPEF

```tcl
if { RCX_RULES && ! SKIP_DETAILED_ROUTE } {
  define_process_corner -ext_model_index 0 X
  extract_parasitics -ext_model_file $::env(RCX_RULES)
  write_spef .../6_final.spef
  read_spef .../6_final.spef
  # IR drop if PWR_NETS_VOLTAGES / GND_NETS_VOLTAGES
} else {
  estimate_parasitics -global_routing   ;# fallback
}
```

Nangate45 in the course **has** RCX: expects SPEF. `head` of `6_final.spef`: `*D_NET`.

IR: `analyze_power_grid` → heatmap `orfs_final_ir_drop.png`. On GCD few mV: M1–M4–M7 PDN is enough. On a mm² die, no.

Then `report_cell_usage`, `report_metrics 6 "finish"` → `6_finish.rpt`.

```tcl
if { [ord::openroad_gui_compiled] } {
  gui::show "source .../save_images.tcl" false
}
```

Headless may fail; the images in `reports/*.webp.png` if there are golden educational (worst path, clocks, congestion). Copied to `gui-shots/orfs_*.png`.

Crash `STA-2204 get_property default`: ORFS **master** vs OpenROAD 26Q2. Tag pinned to 26Q2.

---

## Merge GDS

```
6_final.def + NangateOpenCellLibrary.gds → 6_1_merged.gds → 6_final.gds
```

KLayout stream-out, not OpenROAD. Warning UNITS/DBU: informational if GDS file has size > 0 (`ls -lh 6_final.gds`).

---

## How to read `6_finish.rpt`

| Section | What to copy into the project |
|---|---|
| `report_wns` / `report_tns` | −0.04 / −0.60 |
| `report_clock_min_period` | 0.50 ns vs SDC 0.46 |
| `report_clock_skew` | source/target latency |
| `setup_violation_count` | 38 |
| worst path | start/end FF |

Overlay path: `orfs_final_worst_path.png` (launch cyan, signal red).

---

## Checkpoint

1. Does fill change logic?
2. Why `write_verilog -remove_cells`?
3. Does SPEF without DRT make sense?
4. Why fmax 2.01 GHz with SDC 0.46 ns (~2.17 GHz)?

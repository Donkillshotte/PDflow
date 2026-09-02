# Annotated walkthrough — global_place.tcl e detail_place.tcl

Files: `flow/scripts/global_place.tcl` e `flow/scripts/detail_place.tcl`  
ODB: `3_2_place_iop.odb` → `3_3_place_gp.odb` → (resizer) `3_4` → `3_5_place_dp.odb`

Read this text **with the script open beside you**. Line numbers are from ORFS **26Q2**.

---

## Why two scripts

**Global placement (GP)** spreads cells in the core minimizing wirelength (+ density, optional timing). Cells may **overlap** in the drawing: they are not yet on sites.

**Detailed placement (DP)** legalizes: every instance on a row site, zero overlap, mirroring, optional `improve_placement`.

In between ORFS runs the **resizer** (`3_4_place_resized.odb`): buffer/upsize. Those new buffers *must* go through DP. For this the order is GP → RSZ → DP, not premature DP.

GUI: [gui-atlas.md](./gui-atlas.md) §5.5–5.6 (`win_place_gp.png` vs `win_place_dp.png`).

---

## global_place.tcl — load block (lines 1–5)

```tcl
utl::set_metrics_stage "globalplace__{}"
source $::env(SCRIPTS_DIR)/load.tcl
erase_non_stage_variables place
load_design 3_2_place_iop.odb 2_floorplan.sdc
source_step_tcl PRE GLOBAL_PLACE
```

- Input **IOP already done**: edge pins **pull** the cells. If you compare `3_1_place_gp_skip_io` e `3_3`, internal cells move.
- SDC still `2_floorplan.sdc`: the clock is the same; parasitics not.

Hook `PRE GLOBAL_PLACE`: you can inject Tcl (course: not needed).

---

## dont_use and remove_buffers (lines 7–11)

```tcl
set_dont_use $::env(DONT_USE_CELLS)
if { $::env(GPL_TIMING_DRIVEN) } {
  remove_buffers
}
```

`DONT_USE_CELLS` (platform): forbidden cells (es. excessive drive, latch).  
If GP is timing-driven, ORFS **removes** prior buffers so GP does not optimize an already “polluted” netlist; GP starts clean, RSZ will reinsert.

---

## buffer_ports (lines 17–22)

```tcl
if { ![env_var_exists_and_non_empty FOOTPRINT] } {
  if { !$::env(DONT_BUFFER_PORTS) } {
    buffer_ports {*}[env_var_or_empty BUFFER_PORTS_ARGS]
  }
}
```

On chiplet/`FOOTPRINT` do not buffer ports (other flow). On GCD: **yes**, buffer on ports. I/O pin slew/cap must be legal **before** GP moves everything.

**Advanced experiment:** `DONT_BUFFER_PORTS=1 make place` and check port slew in resizer report.

---

## `global_placement` arguments (lines 24–50)

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
| `-routability_driven` | penalizes regions GRT will hate |
| `-timing_driven` | use estimated slack, not just HPWL |
| `-force_center_initial_place` | starts from die center (GCD: central blob you see in GUI) |
| `phi` min/max | solver step; if min>max → **GPL 200** and stop |

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

- **Density** = fill target. In the course `PLACE_DENSITY_LB_ADDON=0.20` raises the floor: more air, less overflow, a bit more wirelength.
- **Pad** in *sites*: required space between cells (routing). Too much pad → effective utilization rises.

If `global_placement` throws: writes `3_3_place_gp-failed.odb` (lines 63–67). Open in GUI: debug.

Poi `estimate_parasitics -placement` e `report_metrics 3 "global place"`.

Output: `3_3_place_gp.odb`.

**Log `3_3_place_gp.log`:** search for overflow → should tend to 0. If it stays high, density/util/SDC are wrong *before* CTS.

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

| Comando | Role |
|---|---|
| `detailed_placement` | legalizes on sites |
| `improve_placement` | DPO: micro-optimizes legal wirelength |
| `optimize_mirroring` | flip cells (N/S) if LEF allows |
| `check_placement -verbose` | overlap, out-of-row, off-site |

Failure → `3_5_place_dp-failed.odb`. **Not** the same DPL-0038 error as CTS (that is *after* clock buffers, core already full).

Output: `3_5_place_dp.odb` then ORFS copies/aligns to `3_place.odb`.

---

## Cosa guardare in GUI (pixel)

1. `gui_3_3_place_gp.odb` — celle “a nuvola”, visual overlap possible.
2. `gui_3_5_place_dp.odb` — same cells on blue lines.
3. Inspector on an `AND2_X1`: coordinates change between GP and DP (often fractions of µm).

Also see canvas `save_image`: `gui-shots/04_place_gp.png` and `05_place_dp.png`.

---

## Checkpoint

1. Why `load_design` di GP use `3_2_place_iop.odb` e non `2_floorplan.odb`?
2. What measures overflow?
3. `improve_placement` can create overlap? (no: stays legal)
4. Relazione `PLACE_DENSITY_LB_ADDON` ↔ DPL-0038 althe lesson 05?

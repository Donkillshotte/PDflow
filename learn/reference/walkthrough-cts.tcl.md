# Annotated walkthrough — cts.tcl (ORFS 26Q2)

Files: `flow/scripts/cts.tcl`  
Input: `3_place.odb` + `3_place.sdc`  
Output: `4_1_cts.odb`, `4_cts.sdc`  
Educational error artifact: `4_1_error.odb` if `detailed_placement` fails.

GUI: [gui-atlas.md](./gui-atlas.md) §5.7; Inspector on `clk` (§4) after route shows `CTS_NDR_0` — the rule originates here.

---

## Flow (mental map)

```
load 3_place
  repair_clock_inverters
  clock_tree_synthesis          ← inserts CLKBUF* / inverter
  estimate_parasitics -placement
  detailed_placement            ← DPL-0038 lives here
  repair_timing_helper          ← setup/hold with clock already as tree
  detailed_placement again
  check_placement
  report_metrics 4 "cts final"
```

CTS is **not** “add a buffer and done”. It changes the netlist, then **must** re-legalize. If core was at 90% and RSZ+CTS add 15% area, you exceed 100%.

---

## Load and inverters (lines 1–10)

```tcl
load_design 3_place.odb 3_place.sdc
source_step_tcl PRE CTS
repair_clock_inverters
```

`repair_clock_inverters` clones/moves clock inverters **near sinks**. Without this, TritonCTS buffers inverted clocks stupidly (tree on the inverted signal, worse skew).

**Exercise:** in the log `4_1_cts.log` search for `repair_clock_inverters`. Is there output? On GCD it is sometimes silent (few inverted clocks).

---

## save_progress (lines 12–16)

```tcl
proc save_progress { stage } {
  puts "Run 'make gui_$stage.odb' to load progress snapshot"
  orfs_write_db $::env(RESULTS_DIR)/$stage.odb
  orfs_write_sdc $::env(RESULTS_DIR)/$stage.sdc
}
```

When DPL fails, ORFS calls `save_progress 4_1_error`. **Memorize the GUI command** printed in the log. This is the professional debug approach, not blind reruns.

---

## clock_tree_synthesis (lines 18–36)

```tcl
set cts_args [list \
  -sink_clustering_enable \
  -repair_clock_nets]
append_env_var cts_args CTS_BUF_DISTANCE -distance_between_buffers 1
append_env_var cts_args CTS_CLUSTER_SIZE -sink_clustering_size 1
append_env_var cts_args CTS_CLUSTER_DIAMETER -sink_clustering_max_diameter 1
append_env_var cts_args CTS_BUF_LIST -buf_list 1
append_env_var cts_args CTS_LIB_NAME -library 1
if { [env_var_exists_and_non_empty CTS_ARGS] } {
  set cts_args $::env(CTS_ARGS)
}
set_dont_use $::env(DONT_USE_CELLS)
log_cmd clock_tree_synthesis {*}$cts_args
```

| Argument | Educational role |
|---|---|
| `-sink_clustering_enable` | groups nearby FFs → fewer leaves, shorter tree |
| `-repair_clock_nets` | fixes clock nets after insert |
| `CTS_BUF_DISTANCE` | max distance between buffers (capacitance) |
| `CTS_BUF_LIST` | which `CLKBUF_X*` to use |
| `CTS_ARGS` | full override (experts; not needed in course) |

After this command, in GUI `select -name "clkbuf*" -type Inst` must find **more** instances than in `3_place.odb`.

NDR: OpenROAD often applies a **non-default rule** on the clock (wider wire / spacing). In Inspector post-route you see it as `CTS_NDR_0` on the net `clk`.

---

## Parasitics and DPL (lines 38–53)

```tcl
log_cmd estimate_parasitics -placement
...
set_placement_padding -global \
  -left $::env(CELL_PAD_IN_SITES_DETAIL_PLACEMENT) \
  -right $::env(CELL_PAD_IN_SITES_DETAIL_PLACEMENT)
set result [catch { detailed_placement } msg]
if { $result != 0 } {
  save_progress 4_1_error
  error "Detailed placement failed in CTS: $msg"
}
```

CTS buffers have area. `detailed_placement` must find them a site. If `Instances area / core > 1`:

```
[ERROR DPL-0038] Utilization greater than 100%
```

**Fix in the course (one at a time):**

1. `CORE_UTILIZATION=30` (larger core)
2. SDC 0.46 or 2.0 ns (less RSZ pre-CTS)
3. Do not raise density addon in the same run in which you tighten the clock

Playbook: `debug-playbook.md` CTS section. LAB 05 part 4: provoke and fix.

---

## repair_timing post-CTS (lines 61–86)

With **propagated** clock (tree), skew is real. `repair_timing_helper` still inserts *signal* buffers (not just clock) for setup/hold. Then **second** `detailed_placement` + `check_placement -verbose`.

If `EQUIVALENCE_CHECK`/`LEC_CHECK` are on (not in tutorial): dump Verilog pre/post RSZ. Ignore in the course.

`CTS_SNAPSHOTS=1` saves `4_1_pre_repair_hold_setup.odb` — useful if you want GUI *before* repair.

---

## Output and metrics

```tcl
report_metrics 4 "cts final"
orfs_write_db $::env(RESULTS_DIR)/4_1_cts.odb
orfs_write_sdc $::env(RESULTS_DIR)/4_cts.sdc
```

Report: `reports/.../4_cts_final.rpt` — skew, latency, WNS.  
Post-CTS SDC may contain *propagated* latency: it is no longer the “ideal” constraint from lesson 01.

Compare `3_place.sdc` and `4_cts.sdc` (`diff`). What appeared?

---

## GUI — procedure

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_4_cts.odb
```

```tcl
gui::fit
select -name "clk" -type Net
select -name "clkbuf*" -type Inst
```

PNG: `gui-shots/win_cts.png`, `06_cts.png`.

View → Clock Tree Viewer if available; otherwise Inspector on the net is enough for the course.

---

## Checkpoint

1. Why does CTS call `detailed_placement`?
2. Difference `4_1_error.odb` vs `3_5_place_dp-failed.odb`?
3. One config knob that reduces DPL-0038 without touching SDC?
4. What does **skew** measure (one sentence, glossary)?

# Annotated walkthrough — floorplan.tcl (ORFS)

This document explains **line by line** (in blocks) the script ORFS runs in floorplan.
Read it **while** you open the original file in parallel.

Original file: `tools/OpenROAD-flow-scripts/flow/scripts/floorplan.tcl`

---

## Block 1 — Setup stage (lines 1–5)

```tcl
utl::set_metrics_stage "floorplan__{}"
source $::env(SCRIPTS_DIR)/load.tcl
erase_non_stage_variables floorplan
load_design 1_synth.odb 1_synth.sdc
source_step_tcl PRE FLOORPLAN
```

| Line | Meaning |
|---|---|
| `set_metrics_stage` | Tag for QoR metrics (area, util, timing) in the report |
| `load.tcl` | Loads common ORFS helpers |
| `erase_non_stage_variables` | Clears env vars from prior stages (avoids side effects) |
| `load_design` | **Input:** netlist already in DB from synth + consistent SDC |
| `PRE FLOORPLAN` | User hook: you can inject custom Tcl via env variable |

**Exam question:** why is input `1_synth.odb` and not raw Verilog?

---

## Block 2 — Sanity checks (lines 7–43)

- `report_unused_masters` — unused LIB cells (library debug)
- `eliminate_dead_logic` — removes dead logic post-synth
- `check_setup` — checks clock, port, base constraints

**What you learn:** floorplan does not start if setup timing/clock is broken.

**Exercise:** search for `check_setup` in the log `2_1_floorplan.log`. Output OK?

---

## Block 3 — Floorplan method choice (lines 51–64)

ORFS accepts **exactly one** of:

1. `FLOORPLAN_DEF` — import existing DEF
2. `FOOTPRINT` — ICeWall (chiplet style)
3. `DIE_AREA` + `CORE_AREA` — explicit coordinates
4. `CORE_UTILIZATION` — **what we use in the course**

```tcl
set use_core_utilization [env_var_exists_and_non_empty CORE_UTILIZATION]
...
if { $methods_defined > 1 } {
  puts "Error: Floorplan initialization methods are mutually exclusive"
  exit 1
}
```

**In the course:** `CORE_UTILIZATION=35` in config.mk → `initialize_floorplan` computes die/core.

**Experiment:** also add `DIE_AREA` and observe mutual exclusion error.

---

## Block 4 — initialize_floorplan (utilization method)

Typical generated command (see log):

```tcl
initialize_floorplan -utilization 35 -aspect_ratio 1.0 \
  -core_space 1.0 -site FreePDK45_38x28_10R_NP_162NW_34O
```

| Parameter | Educational effect |
|---|---|
| `-utilization 35` | Core uses ~35% of die; rest margins + routing track |
| `-aspect_ratio 1.0` | Square core |
| `-core_space 1.0` | Margin between die edge and core (µm) |
| `-site` | Site type for rows (from PDK) |

**In GUI (`gui_2_1_floorplan.odb`):** zoom out → core rectangle inside die.

Log often shows **IFP-0028**: origin is **snapped** to site grid
(`(1.000, 1.000)` → `(1.140, 1.400)` on the gold run). This is not a bug: without snapping
rows do not align to LEF sites. Note both points in notebook (LAB 03).

---

## Block 5 — Pin placement, macro, tapcell (other scripts)

ORFS floorplan is **multi-step**:

| Step | Script | Output |
|---|---|---|
| 2_1 | floorplan.tcl | init core |
| 2_2 | macro_place.tcl | macro (GCD has none) |
| 2_3 | tapcell.tcl | tap/endcap |
| 2_4 | pdn.tcl + PDN_TCL | power grid |

**Our PDN_TCL:** `grid_strategy-M1-M4-M7.tcl`

PDN concepts:
- `add_pdn_stripe` — VDD/VSS stripes on metal4/metal7
- `add_pdn_connect` — via stacks connect layers
- `define_pdn_grid` — CORE domain

**GUI:** `gui_2_4_floorplan_pdn.odb` → layer metal4/metal7, net VDD/VSS.

---

## What to modify to learn (only one at a time)

| Parameter | Files | Expected effect |
|---|---|---|
| CORE_UTILIZATION 25→55 | config.mk | smaller/larger core |
| aspect_ratio | env or Tcl | rectangular core |
| alternate PDN_TCL | config.mk | different power strategy |
| core_space | platform/tcl | IO margin |

---

## Comprehension checkpoint

Before moving to Lesson 04, you must be able to answer:

1. Four floorplan init methods — which do we use?
2. What distinguishes `2_1_floorplan.odb` vs `2_4_floorplan_pdn.odb`?
3. Where in the log do you find core area in µm²?
4. Why does low utilization help CTS?

If you cannot answer → reread this file + LAB lesson 03.

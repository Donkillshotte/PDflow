# Annotated walkthrough — floorplan.tcl (ORFS)

This document explains **line by line** (in blocks) the script ORFS runs in floorplan.
Leggilo **mentre** open the file originale in parallelo.

Files originale: `tools/OpenROAD-flow-scripts/flow/scripts/floorplan.tcl`

---

## Blocco 1 — Setup stage (righe 1–5)

```tcl
utl::set_metrics_stage "floorplan__{}"
source $::env(SCRIPTS_DIR)/load.tcl
erase_non_stage_variables floorplan
load_design 1_synth.odb 1_synth.sdc
source_step_tcl PRE FLOORPLAN
```

| Riga | Meaning |
|---|---|
| `set_metrics_stage` | Tag for QoR metrics (area, util, timing) in the report |
| `load.tcl` | Carica helper comuni ORFS |
| `erase_non_stage_variables` | Pulisce env vars di fasi precedenti (evita side effect) |
| `load_design` | **Input:** netlist already in DB from synth + consistent SDC |
| `PRE FLOORPLAN` | Hook utente: you can injectare Tcl custom via variable env |

**Exam question:** because input is `1_synth.odb` and not raw Verilog?

---

## Blocco 2 — Sanity checks (righe 7–43)

- `report_unused_masters` — unused LIB cells (library debug)
- `eliminate_dead_logic` — removes dead logic post-synth
- `check_setup` — checks clock, port, base constraints

**What you learn:** floorplan does not start if setup timing/clock is broken.

**Exercise:** search for `check_setup` in the log `2_1_floorplan.log`. Output OK?

---

## Block 3 — Floorplan method choice (lines 51–64)

ORFS accetta **esattamente uno** di:

1. `FLOORPLAN_DEF` — import DEF esistente
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

**Nel course:** `CORE_UTILIZATION=35` in config.mk → initialize_floorplan calcola die/core.

**Experiment:** also add `DIE_AREA` and observe mutual exclusion error.

---

## Blocco 4 — initialize_floorplan (metodo utilization)

Tipico comando generato (see log):

```tcl
initialize_floorplan -utilization 35 -aspect_ratio 1.0 \
  -core_space 1.0 -site FreePDK45_38x28_10R_NP_162NW_34O
```

| Parayardstick | Effetto educational |
|---|---|
| `-utilization 35` | Core uses ~35% of die; rest margins + routing track |
| `-aspect_ratio 1.0` | Core quadrato |
| `-core_space 1.0` | Margine tra die edge e core (µm) |
| `-site` | Site type for rows (from PDK) |

**In GUI (`gui_2_1_floorplan.odb`):** zoom out → rettangolo core dentro die.

Log often shows **IFP-0028**: origin is **snapped** to site grid
(`(1.000, 1.000)` → `(1.140, 1.400)` on the gold run). This is not a bug: without snapping
rows do not align to LEF sites. Note both points in notebook (LAB 03).

---

## Blocco 5 — Pin placement, macro, tapcell (altri script)

Floorplan ORFS is **multi-step**:

| Step | Script | Output |
|---|---|---|
| 2_1 | floorplan.tcl | init core |
| 2_2 | macro_place.tcl | macro (GCD has none) |
| 2_3 | tapcell.tcl | tap/endcap |
| 2_4 | pdn.tcl + PDN_TCL | power grid |

**PDN_TCL nostro:** `grid_strategy-M1-M4-M7.tcl`

Concetti PDN:
- `add_pdn_stripe` — strisce VDD/VSS su metal4/metal7
- `add_pdn_connect` — via stacks connect layers
- `define_pdn_grid` — dominio CORE

**GUI:** `gui_2_4_floorplan_pdn.odb` → layer metal4/metal7, net VDD/VSS.

---

## What to modify to learn (only one at a time)

| Parayardstick | Files | Effetto atteso |
|---|---|---|
| CORE_UTILIZATION 25→55 | config.mk | smaller/larger core |
| aspect_ratio | env o Tcl | core rettangolare |
| PDN_TCL alternativo | config.mk | different power strategy |
| core_space | platform/tcl | margine IO |

---

## Checkpoint comprensione

Before di passare a Lesson 04, you must saper respondsre:

1. Four floorplan init methods — which do we use?
2. Cosa conkeeps `2_1_floorplan.odb` vs `2_4_floorplan_pdn.odb`?
3. Where in the log trovi core area in µm²?
4. Why does low utilization help CTS?

If you cannot answer → reread this file + LAB lesson 03.

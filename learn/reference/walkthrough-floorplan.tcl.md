# Walkthrough annotato — floorplan.tcl (ORFS)

Questo documento spiega **riga per riga** (a blocchi) lo script che ORFS esegue in floorplan.
Leggilo **mentre** apri il file originale in parallelo.

File originale: `tools/OpenROAD-flow-scripts/flow/scripts/floorplan.tcl`

---

## Blocco 1 — Setup stage (righe 1–5)

```tcl
utl::set_metrics_stage "floorplan__{}"
source $::env(SCRIPTS_DIR)/load.tcl
erase_non_stage_variables floorplan
load_design 1_synth.odb 1_synth.sdc
source_step_tcl PRE FLOORPLAN
```

| Riga | Significato |
|---|---|
| `set_metrics_stage` | Tag per metriche QoR (area, util, timing) nel report |
| `load.tcl` | Carica helper comuni ORFS |
| `erase_non_stage_variables` | Pulisce env vars di fasi precedenti (evita side effect) |
| `load_design` | **Input:** netlist già in DB da synth + SDC coerente |
| `PRE FLOORPLAN` | Hook utente: puoi injectare Tcl custom via variable env |

**Domanda d'esame:** perché input è `1_synth.odb` e non il Verilog grezzo?

---

## Blocco 2 — Sanity checks (righe 7–43)

- `report_unused_masters` — celle in LIB non usate (debug libreria)
- `eliminate_dead_logic` — rimuove logica morta post-synth
- `check_setup` — verifica clock, port, constraint base

**Cosa impari:** floorplan non parte se setup timing/clock è rotto.

**Esercizio:** cerca `check_setup` nel log `2_1_floorplan.log`. Output OK?

---

## Blocco 3 — Scelta metodo floorplan (righe 51–64)

ORFS accetta **esattamente uno** di:

1. `FLOORPLAN_DEF` — import DEF esistente
2. `FOOTPRINT` — ICeWall (chiplet style)
3. `DIE_AREA` + `CORE_AREA` — coordinate esplicite
4. `CORE_UTILIZATION` — **quello che usiamo nel corso**

```tcl
set use_core_utilization [env_var_exists_and_non_empty CORE_UTILIZATION]
...
if { $methods_defined > 1 } {
  puts "Error: Floorplan initialization methods are mutually exclusive"
  exit 1
}
```

**Nel corso:** `CORE_UTILIZATION=35` in config.mk → initialize_floorplan calcola die/core.

**Esperimento:** aggiungi anche `DIE_AREA` e osserva errore mutua esclusione.

---

## Blocco 4 — initialize_floorplan (metodo utilization)

Tipico comando generato (vedi log):

```tcl
initialize_floorplan -utilization 35 -aspect_ratio 1.0 \
  -core_space 1.0 -site FreePDK45_38x28_10R_NP_162NW_34O
```

| Parametro | Effetto didattico |
|---|---|
| `-utilization 35` | Core occupa ~35% del die; resto margini + routing track |
| `-aspect_ratio 1.0` | Core quadrato |
| `-core_space 1.0` | Margine tra die edge e core (µm) |
| `-site` | Tipo site per rows (dal PDK) |

**In GUI (`gui_2_1_floorplan.odb`):** zoom out → rettangolo core dentro die.

---

## Blocco 5 — Pin placement, macro, tapcell (altri script)

Floorplan ORFS è **multi-step**:

| Step | Script | Output |
|---|---|---|
| 2_1 | floorplan.tcl | init core |
| 2_2 | macro_place.tcl | macro (GCD non ne ha) |
| 2_3 | tapcell.tcl | tap/endcap |
| 2_4 | pdn.tcl + PDN_TCL | power grid |

**PDN_TCL nostro:** `grid_strategy-M1-M4-M7.tcl`

Concetti PDN:
- `add_pdn_stripe` — strisce VDD/VSS su metal4/metal7
- `add_pdn_connect` — via stack collegano layer
- `define_pdn_grid` — dominio CORE

**GUI:** `gui_2_4_floorplan_pdn.odb` → layer metal4/metal7, net VDD/VSS.

---

## Cosa modificare per imparare (solo uno alla volta)

| Parametro | File | Effetto atteso |
|---|---|---|
| CORE_UTILIZATION 25→55 | config.mk | core più piccolo/grande |
| aspect_ratio | env o Tcl | core rettangolare |
| PDN_TCL alternativo | config.mk | strategia power diversa |
| core_space | platform/tcl | margine IO |

---

## Checkpoint comprensione

Prima di passare a Lezione 04, devi saper rispondere:

1. Quattro metodi di floorplan init — quale usiamo?
2. Cosa contiene `2_1_floorplan.odb` vs `2_4_floorplan_pdn.odb`?
3. Dove nel log trovi core area in µm²?
4. Perché utilization bassa aiuta il CTS?

Se non sai rispondere → rileggi questo file + LAB lezione 03.

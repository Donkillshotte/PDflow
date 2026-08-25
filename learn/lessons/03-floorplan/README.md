# Lezione 03 — Floorplanning

Il floorplan è l'**immobile** del chip: muri (die), stanze (core), pavimento (rows), impianto elettrico (PDN). Le celle logiche **non** sono ancora posizionate: se in GUI cerchi porte NAND, stai nella lezione 04.

Sul GCD `learn` con `CORE_UTILIZATION=35` il log `2_1_floorplan.log` dice circa:

| Metrica | Valore tipico corso |
|---|---|
| Die da utilization | 35%, aspect 1.0 |
| Core area | **1712.5 µm²** |
| Effective utilization | **0.367** |
| Design area (celle) | ~629 µm² (~37% del core) |
| Snapping origin | `(1.000, 1.000)` → `(1.140, 1.400)` (site grid) |

Questi numeri sono il tuo **metro**. Se raddoppi utilization, il core deve restringersi.

## Obiettivi

- Disegnare die vs core vs row vs site e spiegare lo *snapping*
- Usare `CORE_UTILIZATION` sapendo che è mutuamente esclusivo con `DIE_AREA`
- Leggere `grid_strategy-M1-M4-M7.tcl` riga per riga
- Predire perché utilization alta uccide il CTS (ponte lezione 05)

## Letture

- Questo README
- `walkthrough-floorplan.tcl.md` **per intero**
- LAB 03
- `flow/designs/nangate45/gcd/grid_strategy-M1-M4-M7.tcl`
- Atlante: `gui-atlas.md` §5.2–5.4

## Quattro metodi, uno solo

ORFS esce con errore se ne definisci due:

1. `FLOORPLAN_DEF` — importi un DEF già floorplannato
2. `FOOTPRINT` (ICeWall) — chiplet / pad ring
3. `DIE_AREA` + `CORE_AREA` — micrometri espliciti
4. `CORE_UTILIZATION` ← **corso**

```tcl
initialize_floorplan -utilization 35 -aspect_ratio 1.0 \
  -core_space 1.0 -site FreePDK45_38x28_10R_NP_162NW_34O
```

**Formula mentale:** a parità di area celle post-synth,

```
area_core ≈ area_celle / (utilization/100)
```

Utilization **alta** = core **piccolo**. Non “più pieno visivamente” in GUI al passo 2_1: le celle non ci sono ancora. Il pieno lo vedi al CTS.

Lo **site** è la piastrella: larghezza/altezza della libreria. Lo snapping IFP-0028 non è un bug: allinea il core alla griglia.

## Sottofasi

| Step | Output | Cosa impari |
|---|---|---|
| 2_1 | die/core/rows/tracks | geometria vuota (`win_floorplan.png`) |
| 2_2 | macro | GCD: no-op (nessuna SRAM) |
| 2_3 | tapcell | well ties (`win_tapcell.png`) |
| 2_4 | PDN | VDD/VSS (`03_pdn_labeled.png`) |

## PDN — la griglia che userai per sempre

File: `grid_strategy-M1-M4-M7.tcl`

```tcl
set_voltage_domain -name {CORE} -power {VDD} -ground {VSS}
add_pdn_stripe -layer {metal1} -width {0.17} -pitch {2.4} -followpins
add_pdn_stripe -layer {metal4} -width {0.48} -pitch {28.0} -offset {2}
add_pdn_stripe -layer {metal7} -width {1.40} -pitch {15.0} -offset {2}
add_pdn_connect -layers {metal1 metal4}
add_pdn_connect -layers {metal4 metal7}
```

| Pezzo | Ruolo | Cosa vedi in GUI 26Q2 |
|---|---|---|
| `followpins` M1 | rail sulle rows, tocca ogni cella | linee blu fitte |
| strap M4 | distribuzione verticale/orizzontale intermedia | barre verdi (~3 sul GCD) |
| strap M7 | backbone | barre rosa spesse |
| `add_pdn_connect` | via stack tra layer | visibili zoomando gli incroci |

Senza PDN le celle non hanno alimentazione legale. L’IR drop al finish (`orfs_final_ir_drop.png`, scala ~0–5 mV sul GCD) è cieco se la griglia non esiste.

`add_global_connection` collega pin `VDD`/`VSS` delle istanze alle net power: è il motivo per cui non “cablì” a mano VDD su ogni NAND.

## GUI

- `gui_2_1_floorplan.odb`: due rettangoli. **Non** `gui::set_display_controls "Rows"` → GUI-0013.
- `gui_2_4_floorplan_pdn.odb`: spegni metal2/3, resta M1+strap.

## Esperimento obbligatorio

`CORE_UTILIZATION=25` vs `50`, stessa `1_synth.odb` (non rifare synth). Tabella core area dal log `2_1_floorplan.log`.

Predizione: 50% → core ≈ metà di 25% (non esatto: snapping, margins, aspect).

## Errori comuni

- Util 55% + SDC 0.25 ns → DPL-0038 **più tardi**, non al floorplan (il floorplan “verde” ti inganna)
- `DIE_AREA` insieme a `CORE_UTILIZATION` → exit 1 immediato
- PDN “invisibile” = layer spenti
- Confrontare core area tra run senza `clean_floorplan`

## Durata

README+walkthrough 50–70 min, LAB 90–120 min, **totale ~3 ore**.

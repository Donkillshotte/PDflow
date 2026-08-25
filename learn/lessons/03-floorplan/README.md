# Lezione 03 — Floorplanning

Il floorplan è l'**immobile** del chip: muri (die), stanze (core), pavimento (rows), impianto elettrico (PDN). Le celle logiche non sono ancora posizionate.

## Obiettivi

- Disegnare die vs core vs row vs site
- Usare `CORE_UTILIZATION` sapendo che è mutuamente esclusivo con `DIE_AREA`
- Generare e ispezionare PDN
- Predire perché utilization alta uccide il CTS

## Letture

- Questo README
- `walkthrough-floorplan.tcl.md` **per intero**
- LAB 03
- `grid_strategy-M1-M4-M7.tcl`

## Quattro metodi, uno solo

ORFS esce con errore se ne definisci due:

1. `FLOORPLAN_DEF`
2. `FOOTPRINT` (ICeWall)
3. `DIE_AREA` + `CORE_AREA`
4. `CORE_UTILIZATION` ← **corso**

`initialize_floorplan -utilization 35 -aspect_ratio 1.0 -core_space 1.0 -site ...`

Utilization **alta** = core **piccolo** a parità di area celle post-synth.

## Sottofasi

| Step | Output | Cosa impari |
|---|---|---|
| 2_1 | die/core/rows | geometria |
| 2_2 | macro | GCD: no-op |
| 2_3 | tapcell | well ties |
| 2_4 | PDN | VDD/VSS straps |

## PDN in una frase

Metal1 followpin sulle rows + straps metal4/metal7 + via di connessione. Senza PDN le celle non hanno alimentazione legale; IR drop al finish è cieco.

## GUI

- `gui_2_1_floorplan.odb`: Rows ON, Instances OFF
- `gui_2_4_floorplan_pdn.odb`: Nets Power/Ground ON, metal4 ON

Guida click: `gui-openroad.md`.

## Esperimento

`CORE_UTILIZATION=25` vs `50`, stessa synth. Tabella core area dal log `2_1_floorplan.log`.

## Errori comuni

- Util 55% + SDC 0.25 ns → DPL-0038 più tardi (non al floorplan)
- DIE_AREA insieme a UTILIZATION → exit 1 immediato
- PDN “invisibile” = layer spenti, non assente

## Durata

README+walkthrough 50 min, LAB 90–120 min, **totale ~3 ore**.

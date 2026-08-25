# Lezione 03 — Floorplanning

## Obiettivi

- Capire die, core, rows, sites
- Configurare **utilization** e area
- Generare **PDN** (Power Distribution Network)
- Ispezionare tapcells e margini

## Sottofasi floorplan in ORFS

| Step | Output | Script |
|---|---|---|
| 2_1_floorplan | Die/core, rows | `floorplan.tcl` |
| 2_2_floorplan_macro | Macro placement | `macro_place.tcl` |
| 2_3_floorplan_tapcell | Tap/endcap | `tapcell.tcl` |
| 2_4_floorplan_pdn | Power grid | `pdn.tcl` + `PDN_TCL` |

## Parametri chiave

- `CORE_UTILIZATION` — % del die per il core (35% nel corso)
- `DIE_AREA` / `CORE_AREA` — override manuale dimensioni
- `PDN_TCL` — script straps VDD/VSS (metal1 followpin + metal4/7)

## Cosa guardare in GUI

1. **2_1_floorplan** — contorno die, core, rows orizzontali
2. **2_4_floorplan_pdn** — strisce VDD/VSS, followpins M1
3. Layer **Rows**, **PDN**, **Sites** nel Display Control

## Errori comuni

- Utilization troppo alta → CTS/placement falliscono dopo
- Core troppo piccolo → DPL-0038 (utilization > 100%)
- PDN incompleta → IR drop elevato (finish)

## Durata stimata

60–90 minuti.

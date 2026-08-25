# Lezione 00 — Introduzione al Physical Design

Benvenuto nel corso hands-on di **physical design digitale** con OpenROAD.

## Obiettivi

- Capire la mappa **RTL → GDSII**
- Orientarsi in ORFS (OpenROAD-flow-scripts)
- Sapere quali **file** e quali **comandi GUI** userai in ogni fase
- Eseguire un primo smoke test della toolchain

## Il flusso in una riga

```
Verilog (RTL) → Synthesis → Floorplan → Placement → CTS → Routing → Finish → GDS
```

Ogni fase produce artefatti che puoi **aprire in GUI** e **leggere come file**.

## Struttura ORFS (cartelle chiave)

| Cartella | Contenuto |
|---|---|
| `flow/designs/` | Config design (`config.mk`), constraints (`constraint.sdc`), RTL |
| `flow/platforms/nangate45/` | PDK: LEF, LIB, regole tecnologiche |
| `flow/scripts/` | Script Tcl di ogni fase (`floorplan.tcl`, `global_place.tcl`, …) |
| `flow/results/.../learn/` | Snapshot `.odb` del corso (variante `learn`) |
| `flow/logs/.../learn/` | Log dettagliati di ogni step |
| `flow/reports/.../learn/` | Report timing, area, DRC |

## Design didattico: GCD

Il **GCD** (Greatest Common Divisor) è un piccolo core (~250 celle) su **Nangate45** (PDK open). È perfetto per imparare: veloce da eseguire, abbastanza ricco da mostrare placement, CTS e routing reali.

## Due modalità di apprendimento

1. **File / Makefile** — capisci input/output, modifichi parametri, rileggi report
2. **GUI OpenROAD** — ispezioni visivamente layout, timing path, congestione, clock tree

> Per la GUI usa il pulsante **Desktop** su [cursor.com/agents](https://cursor.com/agents) (non le card Preview della chat).

## Artefatti per fase (riferimento rapido)

| Fase | Target make | Snapshot GUI tipico |
|---|---|---|
| Synth | `synth` | `gui_1_synth.odb` |
| Floorplan | `floorplan` | `gui_2_1_floorplan.odb`, `gui_2_4_floorplan_pdn.odb` |
| Place | `place` | `gui_3_3_place_gp.odb`, `gui_3_5_place_dp.odb` |
| CTS | `cts` | `gui_4_1_cts.odb` |
| Route | `route` | `gui_5_1_grt.odb`, `gui_5_2_route.odb` |
| Finish | `finish` | `gui_final` |

## Durata stimata

45–60 minuti (lettura + smoke test).

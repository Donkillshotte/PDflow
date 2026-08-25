# Lezione 07 — Finish, signoff e GDS

Finish non è “un bottone GDS”. È il **contratto con chi viene dopo di te** (foundry, STA signoff, LVS).

## Obiettivi

- Elencare i deliverable e il destinatario di ciascuno
- Distinguere fill (processo) da logica
- Confrontare WNS placement vs SPEF
- Aprire GDS in KLayout

## Letture

- Questo README
- `walkthrough-finish.tcl.md`
- LAB 07
- `file-formats.md` sezioni SPEF/GDS/DEF

## Sottofasi

| Step | Output |
|---|---|
| 6_1_fill | density fill |
| 6_report | `6_final.{odb,def,v,sdc,spef}`, `6_finish.rpt` |
| 6_1_merge | GDS via KLayout `def2stream.py` |

Screenshot GUI (`save_images.tcl`) possono fallire headless: **non** sono il GDS.

## Pacchetto signoff

| File | Ruolo |
|---|---|
| `6_final.gds` | mask |
| `6_final.def` | coordinate / ECO |
| `6_final.v` | LVS / sim |
| `6_final.spef` | STA parassiti |
| `6_final.sdc` | constraints |
| `6_finish.rpt` | WNS TNS power area |

Senza SPEF stai ancora stimando. Con SPEF sei nel mondo post-route.

## Timing: quattro stime

Documenta nel progetto finale:

| Stima | Quando |
|---|---|
| Liberty only | post-synth `sta` |
| Placement RC | post-place |
| Global route RC | post-GRT |
| SPEF | finish |

WNS può **peggiorare** al finish: i fili reali sono più lenti del modello.

## GUI e KLayout

- `gui_final` — worst path, IR drop se heatmap popolata
- `klayout 6_final.gds` — layer, fit

Guida: `gui-atlas.md` (screenshot) e `gui-openroad.md` (menu).

## Progetto finale

`learn/workbook/README.md` esercizio E3 e LAB 07 parte 4.  
Senza quel documento il corso **non è finito**, anche se `make finish` è verde.

## Durata

README+walkthrough 40 min, LAB 90 min, progetto finale 60 min, **totale ~3 ore**.

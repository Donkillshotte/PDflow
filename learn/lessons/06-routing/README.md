# Lezione 06 — Routing

Routing è il passaggio da “celle con pin” a “fili che la fabbrica può stampare”.

## Obiettivi

- Distinguere guide GRT da wire DRT
- Leggere congestion e DRC
- Capire perché il detailed router **non** parte senza GRT
- Antenna rules a livello concettuale

## Letture

- Questo README
- `walkthrough-route.tcl.md`
- LAB 06
- `gui-openroad.md` layer metal

## Due problemi diversi

**Global routing:** assegnare fasce (risorse 2D) minimizzando overflow. Output: `route.guide`.

**Detailed routing:** geometria: width, spacing, via, enclosure. Output: metal in ODB + `5_route_drc.rpt`.

DRT senza guide è come asfaltare senza tracciato.

## Sottofasi ORFS

| Step | Output |
|---|---|
| 5_1_grt | GRT + repair incrementale timing |
| 5_2_route | TritonRoute + antenna |
| 5_3_fillcell | fill post-route |

Nota: GRT **ripara ancora il timing** (`repair_timing_helper`) perché i parassiti da guide sono meglio del placement.

## File

| File | Significato se vuoto/non vuoto |
|---|---|
| `route.guide` | deve essere grande (>0) |
| `5_route_drc.rpt` | vuoto = DRC clean (nel nostro GCD) |
| `5_global_route.rpt` | overflow residue |

## GUI

1. `gui_5_1_grt.odb` — heatmap congestion, guide
2. `gui_5_2_route.odb` — metal1–10 visibili uno alla volta

Esercizio: stessa net, confronta guida vs wire.

## Concetti

- **Congestion:** troppe net / troppi track in un gcell
- **DRC:** regole geometriche PDK
- **Antenna:** carica su gate in etch → diodi, poi ri-route

## Durata

README+walkthrough 40 min, LAB 90 min, **totale ~2.5 ore**.

# Lezione 06 — Routing

## Obiettivi

- Distinguere **global routing** (guide) vs **detailed routing** (wire reali)
- Leggere route guide, report congestione, DRC
- Ispezionare layer metal in GUI
- Capire antenna, filler, spacing rules

## Sottofasi routing ORFS

| Step | Output |
|---|---|
| 5_1_grt | Global route + `route.guide` |
| 5_2_route | Detailed route (TritonRoute) |
| 5_3_fillcell | Fill cells post-route |

## File chiave

- `route.guide` — guida per il detailed router
- `5_2_route.odb` — layout con wire su metal1–metal10
- `reports/5_route_drc.rpt` — violazioni DRC (vuoto = OK)
- `reports/5_global_route.rpt` — overflow/congestion

## GUI

- `gui_5_1_grt.odb` — guide (non wire finali)
- `gui_5_2_route.odb` — routing completo
- Heatmap **Routing Congestion**
- Layer visibility: metal1, via1, metal2, …

## Concetti

- **Congestion** — troppe net in una regione → router fatica
- **DRC** — design rule check (spacing, width, via enclosure)
- **Antenna** — accumulo carica su gate durante fab → fix con diode

## Durata stimata

75–90 minuti.

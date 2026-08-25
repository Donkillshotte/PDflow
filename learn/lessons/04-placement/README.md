# Lezione 04 — Placement

## Obiettivi

- Distinguere **global placement** vs **detailed placement**
- Capire density, overflow, timing-driven resizing
- Leggere report resizer e global place
- Ispezionare legalizzazione in GUI

## Sottofasi placement ORFS

| Step | Cosa fa |
|---|---|
| 3_1_place_gp_skip_io | Global place (I/O esclusi) |
| 3_2_place_iop | I/O placement |
| 3_3_place_gp | Global placement completo |
| 3_4_place_resized | Timing repair: buffer, upsize, clone |
| 3_5_place_dp | Detailed placement (legalizzazione) |

## Metriche da monitorare

- **Placement density** — quanto è pieno il core
- **Overflow** — celle fuori sito (deve → 0 dopo DP)
- **WNS/TNS** post-resize — setup/hold preliminare
- **Buffer count** — celle aggiunte per timing

## GUI — cosa osservare

- `3_3_place_gp.odb` — blob di celle, routing steiner approx
- `3_5_place_dp.odb` — celle allineate alle rows, legali
- Heatmap **Placement Density** (View menu)

## Durata stimata

75–90 minuti.

# Lezione 05 — Clock Tree Synthesis (CTS)

## Obiettivi

- Capire perché serve un **clock tree** equilibrato
- Identificare buffer clock, skew, latency
- Usare **Clock Tree Viewer** in GUI
- Capire interazione CTS ↔ placement ↔ timing

## Cosa fa TritonCTS

1. Parte dal clock root (porta `clk`)
2. Inserisce buffer/inverter per distribuire il clock
3. Bilancia latenza verso tutti i flip-flop
4. Detailed placement post-CTS

## File e report

| Artefatto | Uso |
|---|---|
| `4_1_cts.odb` | Layout post-CTS |
| `4_cts.odb` | Snapshot consolidato |
| `reports/4_cts_final.rpt` | Skew, latency, buffer count |
| `logs/4_1_cts.log` | Dettaglio RSZ + DPL |

## GUI

- Filtra net **clk** / clock nets
- View → **Clock Tree Viewer**
- Confronta `3_place.odb` vs `4_cts.odb`: nuove celle `CLKBUF*`

## Fallimento tipico (didattico)

`DPL-0038 Utilization > 100%` — il resizer pre-CTS ha gonfiato l'area. Soluzioni:
- Abbassare `CORE_UTILIZATION`
- Rilassare `clk_period` in SDC

## Durata stimata

60–90 minuti.

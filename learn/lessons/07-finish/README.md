# Lezione 07 — Finish, signoff e GDS

## Obiettivi

- Completare **fill**, estrazione parassiti, report finale
- Generare **GDSII** per la fabbrica
- Leggere timing post-route con SPEF
- Capire il pacchetto di consegna (GDS + DEF + SDC + SPEF + LIB)

## Sottofasi finish

| Step | Output |
|---|---|
| 6_1_fill | Density fill, tapcell finali |
| 6_report | `6_final.*`, report timing/area |
| 6_1_merge | GDS merge via KLayout |

## File di signoff

| File | Ruolo |
|---|---|
| `6_final.gds` | Layout per mask shop |
| `6_final.def` | Posizioni finali (testo) |
| `6_final.v` | Netlist post-layout |
| `6_final.spef` | Parassiti RC per STA accurata |
| `6_final.sdc` | Constraints |
| `reports/6_finish.rpt` | WNS, TNS, power, area |

## Timing post-route

Con SPEF caricato, OpenSTA calcola delay realistici. Confronta:
- `1_synth` (ideal)
- `3_place` (estimate placement)
- `6_final` (post-route + SPEF)

## Durata stimata

60–90 minuti.

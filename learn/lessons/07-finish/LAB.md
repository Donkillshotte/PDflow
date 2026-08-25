# LAB 07 — Finish e signoff (90 min)

## Parte 1 — Deliverables (20 min)

Dopo `make finish`, verifica ogni file:

| File | Tool | Domanda |
|---|---|---|
| 6_final.gds | KLayout | Quanti layer? |
| 6_final.def | editor | Quanti COMPONENT? |
| 6_final.spef | STA | Perché serve? |
| 6_final.v | sim | Diff vs 1_2_yosys.v? |
| 6_finish.rpt | tu | WNS/TNS? |

## Parte 2 — Timing post-route (25 min)

```bash
rg -n 'slack|WNS|TNS|power|area' reports/nangate45/gcd/learn/6_finish.rpt
```

Confronta WNS con `3_resizer.rpt` e `4_cts_final.rpt`.  
Domanda: peggiora o migliora post-route? Perché (parassiti SPEF)?

## Parte 3 — GUI final (20 min)

`gui_final`:
- Worst path
- IR drop (se heatmap popolata)
- Tutti i layer ON

## Parte 4 — Progetto finale (25 min)

Documento obbligatorio: `learn/workbook/mio-progetto-finale.md`

Contenuto minimo:
1. Parametri scelti (SDC, util)
2. Tabella metriche finali
3. 3 cose imparate
4. 1 errore incontrato e come risolto
5. Prossimo design che porteresti nel flow

## Superamento corso completo

- [ ] Tutte le lezioni 00–07 in `--status`
- [ ] Workbook A2 + D1 completati
- [ ] Progetto finale consegnato

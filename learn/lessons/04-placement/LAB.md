# LAB 04 — Placement (90 min)

## Parte 1 — Teoria (15 min)

**Global placement:** ottimizza wirelength + density; celle possono sovrapporsi visivamente.  
**Detailed placement:** legalizza su sites.  
**Resizer:** buffer/upsize/clone per timing.

## Parte 2 — Run (15 min)

```bash
./scripts/learn_physical_design.sh --lesson 04
```

## Parte 3 — Report (20 min)

Leggi per intero (sì, per intero):
- `reports/.../3_global_place.rpt`
- `reports/.../3_resizer.rpt`

Estrai: WNS, TNS, buffer inserted, resize count.

## Parte 4 — GUI confronto (30 min)

| ODB | Cosa osservare |
|---|---|
| gui_3_3_place_gp.odb | blob, overlap visivo |
| gui_3_4_place_resized.odb | nuove celle buffer |
| gui_3_5_place_dp.odb | allineamento rows |

Heatmap: View → Placement Density

## Parte 5 — Naming resizer (10 min)

In GUI cerca istanze con prefissi:
`hold*`, `rebuffer*`, `fanout*`, `max_cap*`

Spiega cosa significa ciascuno (hint: log resizer).

## Superamento

- [ ] Screenshot o descrizione gp vs dp
- [ ] Tabella metriche resizer nel quaderno

Leggi anche: `learn/reference/walkthrough-global_place.tcl.md` (se presente)

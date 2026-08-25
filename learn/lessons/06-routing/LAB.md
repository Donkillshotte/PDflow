# LAB 06 — Routing (90 min)

## Parte 1 — GRT vs DRT (15 min)

- **Global routing:** crea `route.guide` — corridor per ogni net
- **Detailed routing:** wire reali, rispetta DRC

## Parte 2 — Run route (20 min)

```bash
./scripts/learn_physical_design.sh --lesson 06
```

Verifica:
```bash
wc -l results/nangate45/gcd/learn/route.guide
wc -l reports/nangate45/gcd/learn/5_route_drc.rpt   # 0 = clean
```

## Parte 3 — GUI (30 min)

1. `gui_5_1_grt.odb` — guides colorate, non wire finali
2. `gui_5_2_route.odb` — routing completo

Per ogni net selezionata, annota layer usati (M1? M2? via?).

Heatmap congestion su GRT.

## Parte 4 — KLayout guides (15 min)

```bash
make ... klayout_guides
```

## Parte 5 — Debug routing (10 min)

Se DRC non zero, apri `5_route_drc.rpt` e per ogni violazione:
- layer
- coordinate
- tipo violazione

## Superamento

- [ ] DRC report spiegato
- [ ] Differenza GRT/DRT articolata a voce

# LAB 06 — Routing (90–120 minuti)

GRT decide **dove** posare passare i fili. DRT decide **i fili**. L’atlas §5.8–5.9 is required: i colors M2/M3 are quelli veri di this GUI.

## Measurable objectives

- [ ] `route.guide` not empty; you can say what it is **not**
- [ ] `5_route_drc.rpt` letto (vuoto = clean su GCD)
- [ ] Confrontato `5_1_grt` vs `5_2_route` in GUI or PNG
- [ ] Isolato metal2 e metal3 con Display Control / Tcl
- [ ] Spiegato because `detail_route.tcl` abortisce senza GRT

---

## Part 1 — Two different problems (15 min)

Scrivi analogie tue (non copiare):

| | Global route | Detailed route |
|---|---|---|
| Output | `route.guide` | geometria metal/via in ODB |
| Main constraint | gcell capacity / overflow | width, spacing, via, antenna |
| Accuratezza RC | stima da guide | vicina al SPEF (ancora non estratto) |

Apri `learn/reference/walkthrough-route.tcl.md` e `flow/scripts/global_route.tcl`: find `pin_access`, `global_route`, `estimate_parasitics -global_routing`, il loop incremental con `repair_timing`.

Poi `detail_route.tcl`: guardia `grt::have_routes`, `detailed_route -output_drc`, `repair_antennas`.

---

## Part 2 — Run route (20 min)

Prerequisito: `4_cts.odb`.

```bash
./scripts/learn_physical_design.sh --deep --lesson 06
```

```bash
cd tools/OpenROAD-flow-scripts/flow
wc -l results/nangate45/gcd/learn/route.guide
wc -l reports/nangate45/gcd/learn/5_route_drc.rpt
ls -lh results/nangate45/gcd/learn/5_1_grt.odb \
       results/nangate45/gcd/learn/5_2_route.odb
```

`route.guide` on the GCD is dell’ordine di **migliaia** di righe. If it is 0, GRT failed: open `5_1_grt-failed.odb` e congestion report.

`5_route_drc.rpt`: **0 righe** = no violations listed (il nostro GCD tipicamente is clean). Se >0, per every violazione note layer e tipo.

---

## Part 3 — Leggere una guide (15 min)

```bash
head -40 tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/route.guide
```

Le guide are **fasce 2D** (layer + bounding box), non polilinee mask. In notebook: copia 5 righe and explain cosa pensi che significhino. Poi compare with il walkthrough.

Search for a net che riconosci (`clk`, `req_msg`):

```bash
rg -n 'clk' tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/route.guide | head
```

---

## Part 4 — GUI GRT vs DRT (30 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_5_1_grt.odb
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_5_2_route.odb
```

Procedura pixel (atlas §2 e §5.9):

1. **Fit**.
2. Tcl:

```tcl
gui::set_display_controls "Layers/*" visible false
gui::set_display_controls "Layers/metal2" visible true
gui::fit
```

3. Screenshot mental: direzione dominante M2.
4. Spegnere M2, accendere solo `metal3`.
5. On `5_2_route` wires are **thin and dense**; on GRT you often see more “blocky” corridors.

PNG di riferimento nel repo:

- `gui-shots/win_grt.png`, `07_grt.png`
- `gui-shots/win_route.png`, `08_route_labeled.png`
- `gui-shots/win_layers_m2m3.png` (M2+M3 insieme sul final — stesso gesto)

Heatmap congestion: View → routing congestion se presente. Rosso = gcell saturi.

---

## Part 5 — Antenna e DRC (10 min)

Nel log `5_2_route.log`:

```bash
rg -n 'antenna|DRC|violation|complete' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/5_2_route.log | head -30
```

Cos’is un’antenna (one sentence): charges on gate during etch → diodi / ri-route. You do not need plasma physics: you need to know **ORFS can re-route** after `repair_antennas`.

---

## Part 6 — KLayout guides (optional, 10 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 klayout_guides
```

Se the target manca in this ORFS, apri comunque `6_final.gds` in KLayout e spegni/accendi layer: stesso gesto mental del Display Control.

---

## Pass criteria

- [ ] `wc -l route.guide` annotato
- [ ] DRC spiegato (anche se zero)
- [ ] Difference GRT/DRT articolata **e** agganciata ai PNG/GUI
- [ ] Esperimento metal2-only / metal3-only fatto

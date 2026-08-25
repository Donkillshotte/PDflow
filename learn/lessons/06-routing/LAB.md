# LAB 06 — Routing (90–120 minuti)

GRT decide **dove** possono passare i fili. DRT decide **i fili**. L’atlante §5.8–5.9 è obbligatorio: i colori M2/M3 sono quelli veri di questa GUI.

## Obiettivi misurabili

- [ ] `route.guide` non vuoto; sai dire cosa **non** è
- [ ] `5_route_drc.rpt` letto (vuoto = clean su GCD)
- [ ] Confrontato `5_1_grt` vs `5_2_route` in GUI o PNG
- [ ] Isolato metal2 e metal3 con Display Control / Tcl
- [ ] Spiegato perché `detail_route.tcl` abortisce senza GRT

---

## Parte 1 — Due problemi diversi (15 min)

Scrivi analogie tue (non copiare):

| | Global route | Detailed route |
|---|---|---|
| Output | `route.guide` | geometria metal/via in ODB |
| Vincolo principale | capacità gcell / overflow | width, spacing, via, antenna |
| Accuratezza RC | stima da guide | vicina al SPEF (ancora non estratto) |

Apri `learn/reference/walkthrough-route.tcl.md` e `flow/scripts/global_route.tcl`: trova `pin_access`, `global_route`, `estimate_parasitics -global_routing`, il loop incrementale con `repair_timing`.

Poi `detail_route.tcl`: guardia `grt::have_routes`, `detailed_route -output_drc`, `repair_antennas`.

---

## Parte 2 — Esegui route (20 min)

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

`route.guide` sul GCD è dell’ordine di **migliaia** di righe. Se è 0, GRT è fallito: apri `5_1_grt-failed.odb` e congestion report.

`5_route_drc.rpt`: **0 righe** = nessuna violazione listata (il nostro GCD tipicamente è clean). Se >0, per ogni violazione annota layer e tipo.

---

## Parte 3 — Leggere una guida (15 min)

```bash
head -40 tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/route.guide
```

Le guide sono **fasce 2D** (layer + bounding box), non polilinee mask. Nel quaderno: copia 5 righe e spiega cosa pensi che significhino. Poi confronta con il walkthrough.

Cerca una net che riconosci (`clk`, `req_msg`):

```bash
rg -n 'clk' tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/route.guide | head
```

---

## Parte 4 — GUI GRT vs DRT (30 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_5_1_grt.odb
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_5_2_route.odb
```

Procedura pixel (atlante §2 e §5.9):

1. **Fit**.
2. Tcl:

```tcl
gui::set_display_controls "Layers/*" visible false
gui::set_display_controls "Layers/metal2" visible true
gui::fit
```

3. Screenshot mentale: direzione dominante M2.
4. Spegnere M2, accendere solo `metal3`.
5. Su `5_2_route` i fili sono **sottili e densi**; su GRT spesso vedi corridoi più “a blocchi”.

PNG di riferimento nel repo:

- `gui-shots/win_grt.png`, `07_grt.png`
- `gui-shots/win_route.png`, `08_route_labeled.png`
- `gui-shots/win_layers_m2m3.png` (M2+M3 insieme sul final — stesso gesto)

Heatmap congestion: View → routing congestion se presente. Rosso = gcell saturi.

---

## Parte 5 — Antenna e DRC (10 min)

Nel log `5_2_route.log`:

```bash
rg -n 'antenna|DRC|violation|complete' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/5_2_route.log | head -30
```

Cos’è un’antenna (una frase): carica sul gate durante etch → diodi / ri-route. Non serve la fisica del plasma: serve sapere che **ORFS può ri-routare** dopo `repair_antennas`.

---

## Parte 6 — KLayout guides (opzionale, 10 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 klayout_guides
```

Se il target manca in questa ORFS, apri comunque `6_final.gds` in KLayout e spegni/accendi layer: stesso gesto mentale del Display Control.

---

## Superamento

- [ ] `wc -l route.guide` annotato
- [ ] DRC spiegato (anche se zero)
- [ ] Differenza GRT/DRT articolata **e** agganciata ai PNG/GUI
- [ ] Esperimento metal2-only / metal3-only fatto

# LAB 06 — Routing (90–120 minutes)

GRT decides **where** to route wires. DRT decides **the wires**. Atlas §5.8–5.9 is required: M2/M3 colors are the real ones in this GUI.

## Measurable objectives

- [ ] `route.guide` not empty; you can say what it is **not**
- [ ] `5_route_drc.rpt` read (empty = clean on GCD)
- [ ] Compared `5_1_grt` vs `5_2_route` in GUI or PNG
- [ ] Isolated metal2 and metal3 with Display Control / Tcl
- [ ] Explained why `detail_route.tcl` aborts without GRT

---

## Part 1 — Two different problems (15 min)

Write your own analogies (do not copy):

| | Global route | Detailed route |
|---|---|---|
| Output | `route.guide` | metal/via geometry in ODB |
| Main constraint | gcell capacity / overflow | width, spacing, via, antenna |
| RC accuracy | estimate from guides | close to SPEF (not yet extracted) |

Open `learn/reference/walkthrough-route.tcl.md` and `flow/scripts/global_route.tcl`: find `pin_access`, `global_route`, `estimate_parasitics -global_routing`, the incremental loop with `repair_timing`.

Then `detail_route.tcl`: guard `grt::have_routes`, `detailed_route -output_drc`, `repair_antennas`.

---

## Part 2 — Run route (20 min)

Prerequisite: `4_cts.odb`.

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

`route.guide` on the GCD is on the order of **thousands** of lines. If it is 0, GRT failed: open `5_1_grt-failed.odb` and the congestion report.

`5_route_drc.rpt`: **0 lines** = no violations listed (our GCD is typically clean). If >0, for each violation note layer and type.

---

## Part 3 — Read a guide (15 min)

```bash
head -40 tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/route.guide
```

Guides are **2D bands** (layer + bounding box), not mask polylines. In notebook: copy 5 lines and explain what you think they mean. Then compare with the walkthrough.

Search for a net you recognize (`clk`, `req_msg`):

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

Pixel procedure (atlas §2 and §5.9):

1. **Fit**.
2. Tcl:

```tcl
gui::set_display_controls "Layers/*" visible false
gui::set_display_controls "Layers/metal2" visible true
gui::fit
```

3. Mental screenshot: dominant M2 direction.
4. Turn off M2, turn on only `metal3`.
5. On `5_2_route` wires are **thin and dense**; on GRT you often see more “blocky” corridors.

Reference PNGs in the repo:

- `gui-shots/win_grt.png`, `07_grt.png`
- `gui-shots/win_route.png`, `08_route_labeled.png`
- `gui-shots/win_layers_m2m3.png` (M2+M3 together on final — same gesture)

Congestion heatmap: View → routing congestion if available. Red = saturated gcells.

---

## Part 5 — Antenna and DRC (10 min)

In log `5_2_route.log`:

```bash
rg -n 'antenna|DRC|violation|complete' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/5_2_route.log | head -30
```

What is an antenna (one sentence): charges on gate during etch → diodes / re-route. You do not need plasma physics: you need to know **ORFS can re-route** after `repair_antennas`.

---

## Part 6 — KLayout guides (optional, 10 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 klayout_guides
```

If the target is missing in this ORFS, still open `6_final.gds` in KLayout and toggle layers: same mental gesture as Display Control.

---

## Pass criteria

- [ ] `wc -l route.guide` annotated
- [ ] DRC explained (even if zero)
- [ ] GRT/DRT difference articulated **and** tied to PNGs/GUI
- [ ] metal2-only / metal3-only experiment done

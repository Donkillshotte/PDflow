# Workbook — exercises with assignments and solutions

Notebook course workbook. **Non guardare the solutions** until you have tried.

Solutions (numeri del run d’oro): [solutions.md](./solutions.md).
Table maestra: [golden-metrics.md](../reference/golden-metrics.md).

---

## How to use this workbook

1. Create `learn/workbook/mio-quaderno.md` (copy `notes-template.md`)
2. For each exercise: write hypothesis → run → note results
3. Compare con `solutions.md` **only after**

Tempo recommended total workbook: **3–4 ore** aggiuntive althe lessons.

Non esiste a folder `solutions/`: single file, to avoid spreading spoilers.

---

## Chapter A — Constraints (Lesson 01)

### A1 — Calcolo manual I/O delay
**Assignment:** con `clk_period=0.46` e `clk_io_pct=0.2`, calcola input e output delay.

<details>
<summary>Solution A1</summary>

`0.46 × 0.2 = 0.092 ns` per input e output delay.

</details>

### A2 — Sweep clock period
**Assignment:** run three runs (only through `place`) con:
- `constraint_relaxed.sdc` (2.0 ns)
- default (0.46 ns)
- `constraint_tight.sdc` (0.25 ns)

Fill in table: | SDC | celle post-place | WNS da 3_resizer.rpt | buffer RSZ |

<details>
<summary>Solution A2 (metodo)</summary>

```bash
for sdc in constraint_relaxed.sdc constraint.sdc constraint_tight.sdc; do
  cp learn/designs/nangate45/gcd-tutorial/$sdc learn/designs/nangate45/gcd-tutorial/constraint.sdc
  ./scripts/learn_physical_design.sh --auto --lesson 04  # solo place
  rg 'WNS|Buffer|Resize' tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt | head
done
```

Expected observation: tighter clock → more buffer/upsize → more cells.

</details>

### A3 — Reflective question
**Assignment:** in 5 lines, explain why SDC and floorplan utilization are coupled.

<details>
<summary>Solution A3 (outline)</summary>

Tight clock → resizer adds buffer → cell area grows → same core → effective utilization rises → CTS/legalize fails if >100%.

</details>

---

## Chapter B — Floorplan (Lesson 03)

### B1 — Measure core area
**Assignment:** from `2_1_floorplan.log`, extract Core area per util 30 e 50.

<details>
<summary>Solution B1</summary>

```bash
rg 'Core area' tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/2_1_floorplan.log
```

Higher util → smaller core area (same post-synth cell count).

</details>

### B2 — Hand drawing
**Assignment:** draw on paper die, core, rows, VDD strap. Photograph or describe in notes.

### B3 — GUI scavenger hunt
**Assignment:** in `gui_2_4_floorplan_pdn.odb`, find and note:
- [ ] Net VDD
- [ ] Net VSS  
- [ ] Row site name
- [ ] Un tapcell

---

## Chapter C — Placement (Lesson 04)

### C1 — Global vs Detailed
**Assignment:** compare `gui-shots/win_place_gp.png` e `win_place_dp.png` (o the two GUIs). List 2 visual differences. Fit on both.

### C2 — Count resizer buffers
**Assignment:** da `3_resizer.rpt`, how many buffer/inverter inserted?

<details>
<summary>Solution C2</summary>

Search for lines `Inserted N buffers` in the log `3_4_place_resized.log` o summary in report.

</details>

---

## Chapter D — CTS (Lesson 05)

### D1 — Intentional debug
**Assignment:** cause CTS failure con util 55 + clock 0.25. Document error DPL-0038.

### D2 — Fix
**Assignment:** same scenario, fix with util 30. Does CTS pass?

---

## Chapter E — Routing & Finish (Lezioni 06–07)

### E1 — DRC
**Assignment:** `wc -l 5_route_drc.rpt` — zero lines = clean?

### E2 — GDS
**Assignment:** open GDS in KLayout, count top cells and layers.

### E3 — Final project
**Assignment:** document `mio-progetto-finale.md` with:
- Chosen parameters (SDC, util)
- WNS/TNS/area finali
- GUI screenshot or description
- What you would do differently

---

## Self-assessment grid

| Competenza | Indicatore |
|---|---|
| Beginner | Complete lessons with `--auto` without reading logs |
| Intermediate | Complete workbook A1–C2 with data table |
| Advanced | Debug failed CTS without playbook |
| Expert | Modify an ORFS `.tcl` and explain the effect |

# Workbook solutions — compare **after** trying

Numbers in the «reference» column = run `learn` on this VM
(`CORE_UTILIZATION=35`, SDC 0.46 ns, OpenROAD/ORFS **26Q2**).
Table maestra: [golden-metrics.md](../reference/golden-metrics.md).

Your values may differ by a few percent. If deviation > 20% on cells/area,
you used wrong variant, SDC or PDK — open the [debug-playbook](../reference/debug-playbook.md).

---

## A1 — I/O delay

`0.46 × 0.2 = 0.092 ns` sia in input sia in output.

Nel file: `set_input_delay` / `set_output_delay` usano `[expr $clk_period * $clk_io_pct]`.

## A2 — Sweep clock (through `place`)

Procedure (one SDC at a time; **restore** default at the end):

```bash
cp learn/designs/nangate45/gcd-tutorial/constraint.sdc \
   learn/workbook/backup-sdc-default.sdc
cd tools/OpenROAD-flow-scripts/flow
# for every SDC file:
cp ../../../../learn/designs/nangate45/gcd-tutorial/constraint_relaxed.sdc \
   ../../../../learn/designs/nangate45/gcd-tutorial/constraint.sdc
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 \
     clean_synth clean_floorplan clean_place
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 synth floorplan place
rg -n 'worst slack|Inserted|period_min' \
  reports/nangate45/gcd/learn/3_resizer.rpt \
  logs/nangate45/gcd/learn/3_4_place_resized.log | head
```

| SDC | Periodo | Cosa attenderti a place (qualitativo) | Default `learn` (0.46 ns) |
|---|---|---|---|
| relaxed | 2.0 ns | wide positive WNS, few RSZ buffers | — |
| default | 0.46 ns | worst slack **+0.01 ns**, `period_min` **0.45 ns**, area **684 µm² / 40%** | this riga |
| tight | 0.25 ns | more buffer/upsize; CTS may hit **DPL-0038** after | is not the row d’oro |

Observation: tighter clock → more RSZ work → more area on the **same** core.

Restore:

```bash
cp learn/workbook/backup-sdc-default.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
```

## A3 — SDC e utilization accoppiati

Tight clock → negative slack → RSZ inserts buffer/upsize → cell area grows →
`CORE_UTILIZATION` fixes core → *effective* utilization rises → at CTS
`detailed_placement` may hit **DPL-0038** (util > 100%).

On the healthy run you are at **48.3%** post-CTS, not at 100%. DPL-0038 is l’LAB 05 part 4 experiment
(util 55 + SDC 0.25), **non** the table d’oro.

---

## B1 — Core area vs utilization

Dal log `2_1_floorplan.log`, riga `Core area`.

Riferimento **util 35**: **1712.5 µm²**, effective util **0.367**.

Mental formula: `area_core ≈ cell_area / (utilization/100)`.
With the same 629 µm² of cells, util 50 → core ≈ half of util 25
(not exact: snapping **IFP-0028**, margins, aspect 1.0).

## B2 — Disegno

Outer die, inner core, horizontal rows, M1 rails on rows,
M4/M7 mesh straps. Compare with PNG `gui-shots/03_pdn_labeled.png`.

## B3 — GUI scavenger (PDN)

| Cosa | Where |
|---|---|
| VDD / VSS | Inspector on a strap; `Nets/Power` and `Nets/Ground` |
| Site | log `2_1`: `FreePDK45_38x28_10R_NP_162NW_34O` |
| Tapcell | `gui_2_3_floorplan_tapcell.odb` or PNG `win_tapcell.png` |

Non usare `gui::set_display_controls "Rows"` → **GUI-0013**.

---

## C1 — GP vs DP

| Vista | PNG | Cosa see |
|---|---|---|
| GP | `win_place_gp.png`, `04_place_gp_labeled.png` | blob, possible visual overlap, I/O triangles |
| DP | `win_place_dp.png`, `05_place_dp.png` | aligned to rows, overlap gone |

## C2 — Buffer resizer a place

Search for `Inserted` in `logs/.../3_4_place_resized.log`.
Area post-resize riferimento: **684 µm² / 40%** (era ~629 / 37% post-synth).
I **45** buffer annotati in golden-metrics are del **CTS**, not from this step:
do not mix i due `Inserted`.

---

## D1 — Intentionat DPL-0038

`constraint_tight.sdc` (0.25 ns) + `CORE_UTILIZATION=55` → atteso **DPL-0038**
in `4_1_cts.log`. Snapshot: `4_1_error.odb`.

This is not **RSZ-0062**: 0062 = timing not repaired (il run d’oro lo ha, e **passa**);
0038 = legalize impossible because area > core.

## D2 — Fix

Only one: `CORE_UTILIZATION=30` **or** SDC 0.46/2.0 ns. Then CTS must pass.
Restore SDC e util 35 before of the lesson 06.

---

## E1 — DRC

`wc -l reports/nangate45/gcd/learn/5_route_drc.rpt` → **0** on the GCD `learn` = no violations listed.

## E2 — GDS

`klayout results/.../6_final.gds`, tasto F. Top cells ≥ 1, metal layers visible.
Colori **≠** Display Control Qt.

## E3 — Final project

Template: `progetto-finale-template.md`. Must compare `period_min`
finish (**0.50 ns** ~ **2011 MHz**) with SDC 0.46 ns (~2174 MHz):
`make finish` green **non** chiude 2.17 GHz.

PNGs to cite: `orfs_final_worst_path.png`, `orfs_cts_clock_tree.png`,
`orfs_final_ir_drop.png`, `03_pdn_labeled.png`.

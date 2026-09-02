# Golden metrics — reference `learn` run

A **complete** flow on the tutorial (`CORE_UTILIZATION=35`, `constraint.sdc` 0.46 ns,
OpenROAD **26Q2**, ORFS **26Q2**).

Your numbers may differ by a few percent (threads, seed). If they diverge by
**an order of magnitude**, you used the wrong variant, SDC, or PDK.

## Single command (from the `flow/` folder)

Copy **in full**. Never `make ...` with ellipsis: without `DESIGN_CONFIG` and `FLOW_VARIANT=learn`
ORFS falls back to upstream GCD (different util, `base` folder).

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>
```

`<target>`: `synth` | `floorplan` | `place` | `cts` | `route` | `finish` | `gui_<stem>.odb`

Clean one phase: `clean_synth` … `clean_finish` or `clean_all` (not `make clean`:
in this ORFS it is disabled).

---

## Master table

| Stage | Files | What to note | Reference value |
|---|---|---|---|
| Synth | `synth_stat.txt` | cells / area / DFF_X1 | **496** / **628.824** / **35** |
| Floorplan | `2_1_floorplan.log` | Core area / eff. util | **1712.5 µm²** / **0.367** |
| Floorplan | same log | Design area | **629 µm² ~37%** |
| Place resize | `3_4_place_resized.log` | Design area | **684 µm² 40%** |
| Place | `3_resizer.rpt` | worst slack max | **+0.01 ns** (0 viol setup) |
| Place | same | `period_min` / fmax | **0.45 ns** / ~**2240 MHz** |
| CTS DPL | `4_1_cts.log` `DPL-0006` | util pre-repair | **40.5%** (693 / 1712 µm²) |
| CTS RSZ | same log | buffer / warning | **Inserted 45**, **RSZ-0062** |
| CTS DPL | same | util post-repair | **48.3%** (828 µm²) |
| CTS | `4_cts_final.rpt` | WNS / viol / skew | **−0.04** / **32** / ~**0.00** |
| GRT | `5_global_route.rpt` | WNS / viol | **−0.05** / **43** |
| DRC | `5_route_drc.rpt` | `wc -l` | **0** (clean) |
| Finish | `6_finish.rpt` | WNS / TNS / viol | **−0.04** / **−0.60** / **38** |
| Finish | same | `period_min` / fmax | **0.50 ns** / ~**2011 MHz** |
| Finish | same | setup skew | ~**0.00** |
| IR drop | `orfs_final_ir_drop.png` | scale | ~**0–5.2 mV** |

Required reading: **fmax finish (2.01 GHz) < 1/0.46 (2.17 GHz)**.
`make finish` green ≠ timing closed at the SDC period.

`period_min` is the smallest period for which STA does **not** see negative WNS
(with that RC model). fmax ≈ `1000 / period_min` in MHz if `period_min` is in ns.

**Ideal** clock at place (`period_min` 0.45) vs **propagated** clock + SPEF at finish (0.50):
the extra 0.05 ns is wires + tree, not a bug.

**RSZ-0062** on this run is expected: the CTS resizer does not close all setup.
Placement stays legal (util 48%, not 100%). **DPL-0038** is a different error
(LAB 05 part 4).

---

## How to extract fields (copy-paste)

From `tools/OpenROAD-flow-scripts/flow`:

```bash
rg -n 'Number of cells|Chip area|DFF_X1' reports/nangate45/gcd/learn/synth_stat.txt
rg -n 'Core area|Effective utilization|Design area' logs/nangate45/gcd/learn/2_1_floorplan.log
rg -n 'worst slack|period_min|setup violation' reports/nangate45/gcd/learn/3_resizer.rpt
rg -n 'Inserted|DPL-0006|RSZ-0062' logs/nangate45/gcd/learn/4_1_cts.log
rg -n 'worst slack|setup violation|skew' reports/nangate45/gcd/learn/4_cts_final.rpt
wc -l reports/nangate45/gcd/learn/5_route_drc.rpt
rg -n 'wns max|tns max|period_min|setup violation' reports/nangate45/gcd/learn/6_finish.rpt
```

---

## Clock tree (viewer)

PNG: `gui-shots/orfs_cts_clock_tree.png`

- Leaf latency ~ **0.07 ns**
- Second level ~ **fanout 4**
- Leaves aligned in Y → small skew (consistent with report ~0)

---

## What is not “golden”

- Run `FLOW_VARIANT=base` or `designs/nangate45/gcd` **without** `-tutorial`
- Tight SDC 0.25 ns + util 55 → **DPL-0038** (LAB 05 exercise, not this table)
- Yosys without Tcl / ORFS master vs OpenROAD 26Q2 (`STA-2204`)

---

## How to use it in the notebook

For every lesson: copy the table row, put **your value** next to it,
percent delta. If delta > 20% on area/cells, stop and open the playbook.
The final project uses the same grid in `workbook/progetto-finale-template.md`.

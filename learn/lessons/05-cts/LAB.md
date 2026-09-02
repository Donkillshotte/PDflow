# LAB 05 — CTS (90–120 minute session)

Bring open: README 05, `walkthrough-cts.tcl.md`, `gui-atlas.md` §5.7 and §9, CTS playbook.

Parenthetical numbers are from a reference `learn` run (util 35, 0.46 ns). **Your** numbers may differ: note yours.

## Measurable objectives

- [ ] Skew and latency read from `4_cts_final.rpt`
- [ ] `CLKBUF*` counted (GUI or `rg`) pre vs post
- [ ] Clock tree explained using `orfs_cts_clock_tree.png` or Viewer
- [ ] DPL-0038 triggered **and** fixed, documented

---

## Part 1 — Theory with viewer (20 min)

Open `learn/reference/gui-shots/orfs_cts_clock_tree.png`.

In notebook:

| PNG element | What it represents | Approximate value (ns) |
|---|---|---|
| Triangolo rosso in alto | root clock | ~0 |
| Blue triangles | `CLKBUF` levels | |
| Squares at bottom | sinks (FF CK) | ~0.07 |
| Vertical leaf spread | **skew** | small if aligned |

Compare con README: fanout ~4 al secondo livello. If your tree differs, that is not an error: clustering depends on sinks.

Reread `cts.tcl` blocchi `clock_tree_synthesis` e `detailed_placement` (walkthrough).

---

## Part 2 — Baseline CTS (15 min)

Prerequisito: `3_place.odb`.

```bash
./scripts/learn_physical_design.sh --deep --lesson 05
```

O:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 cts
```

Se fallisce → Part 4. Se passa:

```bash
rg -n 'DPL-0006|Inserted|RSZ-0062|worst slack' \
  logs/nangate45/gcd/learn/4_1_cts.log \
  reports/nangate45/gcd/learn/4_cts_final.rpt | head -40
```

Riferimento: util 40.5% → 48.3%, `Inserted 45 buffers`, possible **RSZ-0062**, WNS −0.04.  
RSZ-0062 **non** is DPL-0038: placement is legale, the timing no.

---

## Part 3 — GUI e conteggio buffer (25 min)

```bash
# Pre
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_place.odb
# Post (another shell, stesso cwd):
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_4_cts.odb
```

Tcl:

```tcl
select -name "clkbuf*" -type Inst
select -name "clk" -type Net
```

O da shell sul Verilog/ODB dump:

```bash
rg -c 'CLKBUF' results/nangate45/gcd/learn/3_place.sdc
# meglio: netlist o report cell usage
rg -c 'CLKBUF_' results/nangate45/gcd/learn/6_final.v || true
```

Checklist atlas:

- [ ] `win_cts.png` vs your window
- [ ] Inspector net `clk` after route: `CTS_NDR_0` (lesson 07, ma the rule originates here)
- [ ] View → Clock Tree Viewer **or** PNG `orfs_cts_clock_tree.png`

Note: additional clock buffers ≈ ______.

---

## Part 4 — Intentional debug DPL-0038 (35 min)

**Un parayardstick per volta.** Backup SDC.

```bash
cp learn/designs/nangate45/gcd-tutorial/constraint.sdc \
   learn/workbook/backup-sdc-default.sdc
cp learn/designs/nangate45/gcd-tutorial/constraint_tight.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
```

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=55 \
     clean_synth clean_floorplan clean_place clean_cts
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=55 synth floorplan place cts
```

Expected: **DPL-0038** (o fail affine) in `4_1_cts.log`.

```bash
rg -n 'DPL-0038|DPL-0006|Utilization greater' \
  logs/nangate45/gcd/learn/4_1_cts.log
```

If it exists `4_1_error.odb`:

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_4_1_error.odb
```

**Fix (pick ONE, document the others as hypotheses):**

- A: `CORE_UTILIZATION=30` + SDC tight
- B: SDC default 0.46 + util 55
- C: entrambi rilassati (controllo positivo)

Restore:

```bash
cp learn/workbook/backup-sdc-default.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
```

Workbook D1/D2. Log: template in `debug-playbook.md`.

---

## Part 5 — Report (15 min)

```bash
sed -n '1,40p' tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/4_cts_final.rpt
```

Fill in:

| Campo | Valore |
|---|---|
| WNS | |
| setup skew | |
| source/target latency (first two skew rows) | |
| setup violation count | |

Compare with finish (`6_finish.rpt`): skew stays small, violations remain. Why? (signal RC, not just clock)

---

## Part 6 — Written exam (10 min)

1. Why CTS calls `detailed_placement`?
2. Difference RSZ-0062 vs DPL-0038?
3. One knob that reduces DPL-0038 **without** touching SDC?
4. What does the Y spread of leaves in the clock tree PNG measure?

---

## Pass criteria

- [ ] Baseline CTS executed
- [ ] Table DPL-0006 / WNS
- [ ] DPL-0038 documented (or explained because it *did not* appear: utilization already low)
- [ ] Clock tree described
